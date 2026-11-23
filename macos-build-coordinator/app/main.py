import hmac
import os
import re
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, ConfigDict

from app import store

MAX_IPA_BYTES = 100 * 1024 * 1024
MAX_LOG_CHUNK = 1024 * 1024
REQUEST_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
REVISION = re.compile(r"^[A-Za-z0-9._/-]{1,128}$")
SUBDIR = re.compile(r"^[A-Za-z0-9._/-]{1,200}$")
SHA = re.compile(r"^[0-9a-fA-F]{7,64}$")
STATUS_TOKEN = re.compile(r"^[a-z0-9-]{0,40}$")


class BuildCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    build_request_id: str
    source_url: str
    source_revision: str
    source_subdirectory: str = ""
    react_native_version: str
    script_set: str


class CompleteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resolved_sha: str = ""
    ipa_status: str = ""
    log_tail: str = ""


class FailBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    error: str
    ipa_status: str = ""
    log_tail: str = ""


def reject(status, detail):
    raise HTTPException(status_code=status, detail=detail)


def validate_source_url(value):
    if not isinstance(value, str) or len(value) > 500:
        reject(400, "SOURCE_URL inválida.")
    if any(char in value for char in "\n\r\t `\"'$|&;<>\\"):
        reject(400, "SOURCE_URL inválida.")
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        reject(400, "SOURCE_URL precisa ser https, sem usuário e senha na URL.")
    return value


def validate_revision(value):
    if not isinstance(value, str) or not REVISION.fullmatch(value) or value.startswith("-") or ".." in value:
        reject(400, "A revisão precisa ser um commit, uma branch ou uma tag.")
    return value


def validate_subdirectory(value):
    if value == "":
        return ""
    if (
        not isinstance(value, str)
        or value.startswith("/")
        or "\\" in value
        or ".." in value
        or not SUBDIR.fullmatch(value)
    ):
        reject(400, "A pasta da aplicação é inválida.")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        reject(400, "A pasta da aplicação é inválida.")
    return value


def validate_create(body):
    if not REQUEST_ID.fullmatch(body.build_request_id):
        reject(400, "O identificador do pedido é inválido.")
    if body.script_set != store.ALLOWED_SCRIPT_SET:
        reject(400, "script_set não autorizado.")
    if body.react_native_version not in store.ALLOWED_RN:
        reject(400, "Esta pilha React Native não é compilada neste Mac.")
    return {
        "build_request_id": body.build_request_id,
        "source_url": validate_source_url(body.source_url),
        "source_revision": validate_revision(body.source_revision),
        "source_subdirectory": validate_subdirectory(body.source_subdirectory),
        "react_native_version": body.react_native_version,
        "script_set": body.script_set,
    }


def bearer(request):
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        reject(401, "Credencial ausente.")
    return token


def require_role(request, env_name):
    expected = os.environ.get(env_name, "")
    received = bearer(request)
    if not expected or not hmac.compare_digest(received, expected):
        reject(401, "Credencial rejeitada.")


def require_tekton(request):
    require_role(request, "TEKTON_TOKEN")


def require_agent(request):
    require_role(request, "AGENT_TOKEN")


def lease_of(request):
    token = request.headers.get("x-build-lease", "")
    if not token:
        reject(401, "Lease ausente.")
    return token


def lease_error(state):
    if state == "missing":
        reject(404, "Build não encontrado.")
    reject(409, "O lease não corresponde a um build em execução.")


def bounded_text(value, limit, label):
    if not isinstance(value, str) or len(value) > limit or "\x00" in value:
        reject(400, label)
    return value


@asynccontextmanager
async def lifespan(_app):
    if not os.environ.get("TEKTON_TOKEN") or not os.environ.get("AGENT_TOKEN"):
        raise RuntimeError("TEKTON_TOKEN e AGENT_TOKEN são obrigatórios.")
    store.init_db()
    yield


app = FastAPI(title="macOS Build Coordinator", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def request_error(_request, _exc):
    return JSONResponse(status_code=422, content={"detail": "O pedido tem campos inválidos ou não permitidos."})


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/builds", status_code=201)
def create_build(body: BuildCreate, request: Request):
    require_tekton(request)
    fields = validate_create(body)
    kind, row = store.create_build(fields)
    if kind == "conflict":
        reject(409, "Já existe um build com esse identificador e outros parâmetros.")
    status = 201 if kind == "created" else 200
    return JSONResponse(status_code=status, content=row)


@app.get("/builds/{build_id}")
def read_build(build_id: str, request: Request):
    require_tekton(request)
    row = store.get_build(build_id)
    if row is None:
        reject(404, "Build não encontrado.")
    return row


@app.get("/builds/{build_id}/artifact")
def download_artifact(build_id: str, request: Request):
    require_tekton(request)
    row = store.get_build(build_id)
    if row is None:
        reject(404, "Build não encontrado.")
    path = store.artifact_path(build_id)
    if row["status"] != "succeeded" or not row["artifact_ready"] or not path.is_file():
        reject(404, "IPA indisponível.")
    return FileResponse(path, media_type="application/octet-stream", filename="app.ipa")


@app.post("/builds/claim")
def claim(request: Request):
    require_agent(request)
    job = store.claim_job()
    if job is None:
        return Response(status_code=204)
    return job


@app.post("/builds/{build_id}/log")
async def append_build_log(build_id: str, request: Request):
    require_agent(request)
    payload = await request.body()
    if len(payload) > MAX_LOG_CHUNK:
        reject(413, "O trecho de log excede o limite.")
    text = payload.decode("utf-8", errors="replace").replace("\x00", "")
    if not text:
        return Response(status_code=204)
    state, size = store.append_log(build_id, lease_of(request), text)
    if state != "ok":
        lease_error(state)
    return {"bytes": size}


@app.get("/builds/{build_id}/log")
def read_build_log(build_id: str, request: Request, offset: int = 0):
    require_tekton(request)
    if offset < 0:
        reject(400, "O offset do log é inválido.")
    found = store.read_log(build_id, offset)
    if found is None:
        reject(404, "Build não encontrado.")
    chunk, size, reset = found
    return Response(
        content=chunk,
        media_type="text/plain; charset=utf-8",
        headers={"X-Log-Size": str(size), "X-Log-Reset": "1" if reset else "0"},
    )


@app.post("/builds/{build_id}/heartbeat")
def heartbeat(build_id: str, request: Request):
    require_agent(request)
    state = store.heartbeat(build_id, lease_of(request))
    if state != "ok":
        lease_error(state)
    return {"status": "running"}


@app.put("/builds/{build_id}/artifact")
async def upload_artifact(build_id: str, request: Request):
    require_agent(request)
    lease = lease_of(request)
    payload = await request.body()
    if len(payload) > MAX_IPA_BYTES:
        reject(413, "IPA acima do limite.")
    if len(payload) < 4 or payload[:2] != b"PK":
        reject(400, "O artefato não é um IPA.")
    state = store.save_artifact(build_id, lease, payload)
    if state != "ok":
        lease_error(state)
    return {"artifact_ready": True}


@app.post("/builds/{build_id}/complete")
def complete(build_id: str, body: CompleteBody, request: Request):
    require_agent(request)
    resolved = body.resolved_sha
    if resolved and not SHA.fullmatch(resolved):
        reject(400, "O commit resolvido é inválido.")
    if not STATUS_TOKEN.fullmatch(body.ipa_status):
        reject(400, "ipa_status é inválido.")
    log_tail = bounded_text(body.log_tail, store.MAX_LOG, "O log excede o limite.")
    state, row = store.finish(
        build_id,
        lease_of(request),
        "succeeded",
        "",
        resolved,
        body.ipa_status,
        log_tail,
    )
    if state == "no-artifact":
        reject(409, "O build não tem IPA.")
    if state != "ok":
        lease_error(state)
    return row


@app.post("/builds/{build_id}/fail")
def fail(build_id: str, body: FailBody, request: Request):
    require_agent(request)
    error = bounded_text(body.error.strip(), 2000, "O erro precisa ser informado.")
    if not error:
        reject(400, "O erro precisa ser informado.")
    if not STATUS_TOKEN.fullmatch(body.ipa_status):
        reject(400, "ipa_status é inválido.")
    log_tail = bounded_text(body.log_tail, store.MAX_LOG, "O log excede o limite.")
    state, row = store.finish(
        build_id,
        lease_of(request),
        "failed",
        error,
        "",
        body.ipa_status,
        log_tail,
    )
    if state != "ok":
        lease_error(state)
    return row
