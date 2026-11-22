#!/usr/bin/env python3
# Agente local do build iOS. Só executa os scripts versionados em ios-build/ci.
import json
import re
import shutil
import ssl
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

SCRIPT_SET = "ios-build-v1"
ALLOWED_RN = ("rn-0.87.1", "rn-0.88.1")
SCRIPTS = (
    "checkout-source.sh",
    "prepare-node.sh",
    "prepare-pods.sh",
    "discover-xcode.sh",
    "build-simulator.sh",
    "archive-device.sh",
    "collect-ipa.sh",
)
REVISION = re.compile(r"^[A-Za-z0-9._/-]{1,128}$")
SUBDIR = re.compile(r"^[A-Za-z0-9._/-]{1,200}$")
SHA = re.compile(r"^[0-9a-fA-F]{7,64}$")
REQUEST_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
MAX_LOG = 65536


class JobRejected(Exception):
    pass


class JobFailed(Exception):
    def __init__(self, message, ipa_status=""):
        super().__init__(message)
        self.ipa_status = ipa_status


def validate_job(job):
    if not isinstance(job, dict):
        raise JobRejected("O job não tem o formato esperado.")
    if job.get("script_set") != SCRIPT_SET:
        raise JobRejected("script_set não autorizado.")
    if job.get("react_native_version") not in ALLOWED_RN:
        raise JobRejected("Esta pilha React Native não é compilada neste Mac.")
    request_id = job.get("build_request_id", "")
    if not isinstance(request_id, str) or not REQUEST_ID.fullmatch(request_id):
        raise JobRejected("O identificador do pedido é inválido.")
    source_url = job.get("source_url", "")
    if not isinstance(source_url, str) or len(source_url) > 500:
        raise JobRejected("SOURCE_URL inválida.")
    if any(char in source_url for char in "\n\r\t `\"'$|&;<>\\"):
        raise JobRejected("SOURCE_URL inválida.")
    parsed = urlparse(source_url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise JobRejected("SOURCE_URL precisa ser https, sem usuário e senha na URL.")
    revision = job.get("source_revision", "")
    if not isinstance(revision, str) or not REVISION.fullmatch(revision) or revision.startswith("-") or ".." in revision:
        raise JobRejected("A revisão precisa ser um commit, uma branch ou uma tag.")
    subdirectory = job.get("source_subdirectory") or ""
    if subdirectory:
        if (
            not isinstance(subdirectory, str)
            or subdirectory.startswith("/")
            or "\\" in subdirectory
            or ".." in subdirectory
            or not SUBDIR.fullmatch(subdirectory)
            or any(part in ("", ".", "..") for part in subdirectory.split("/"))
        ):
            raise JobRejected("A pasta da aplicação é inválida.")
    build_id = job.get("id", "")
    lease = job.get("lease_token", "")
    if not isinstance(build_id, str) or not re.fullmatch(r"[0-9a-f-]{36}", build_id):
        raise JobRejected("O identificador do build é inválido.")
    if not isinstance(lease, str) or not re.fullmatch(r"[0-9a-f-]{36}", lease):
        raise JobRejected("O lease é inválido.")
    return {
        "id": build_id,
        "lease_token": lease,
        "build_request_id": request_id,
        "source_url": source_url,
        "source_revision": revision,
        "source_subdirectory": subdirectory,
        "react_native_version": job["react_native_version"],
        "script_set": SCRIPT_SET,
    }


def script_list(script_dir):
    root = Path(script_dir).resolve()
    paths = []
    for name in SCRIPTS:
        path = (root / name).resolve()
        if path.parent != root or not path.is_file():
            raise JobRejected(f"Script autorizado ausente: {name}")
        paths.append(path)
    return paths


def build_env(job, workspace, path):
    return {
        "PATH": path,
        "HOME": str(Path.home()),
        "USER": Path.home().name,
        "LOGNAME": Path.home().name,
        "LANG": "en_US.UTF-8",
        "LC_ALL": "en_US.UTF-8",
        "TERM": "dumb",
        "TMPDIR": "/tmp",
        "CI_PROJECT_DIR": str(workspace),
        "SOURCE_URL": job["source_url"],
        "SOURCE_SHA": job["source_revision"],
        "SOURCE_SUBDIRECTORY": job["source_subdirectory"],
        "RN_VERSION": job["react_native_version"],
        "BUILD_REQUEST_ID": job["build_request_id"],
        "GIT_TERMINAL_PROMPT": "0",
    }


def resolved_sha(workspace):
    path = workspace / "build.env"
    if not path.is_file():
        return ""
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("SOURCE_SHA="):
            continue
        value = line.split("=", 1)[1].strip()
        if len(value) >= 2 and value[0] == "'" and value[-1] == "'":
            value = value[1:-1]
        if SHA.fullmatch(value):
            return value.lower()
    return ""


def ipa_status(workspace):
    for candidate in (workspace / "output" / "signing-status.txt", workspace / "signing-status.txt"):
        if not candidate.is_file():
            continue
        for line in candidate.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("IPA_STATUS="):
                value = line.split("=", 1)[1].strip()
                if re.fullmatch(r"[a-z0-9-]{1,40}", value):
                    return value
    return ""


def log_tail(path):
    if not path.is_file():
        return ""
    data = path.read_bytes()[-MAX_LOG:]
    return data.decode("utf-8", errors="replace")


class CoordinatorClient:
    def __init__(self, base_url, token_file, ca_file=""):
        parsed = urlparse(base_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise JobRejected("O coordenador precisa ser acessado por HTTPS.")
        self.base = base_url.rstrip("/")
        self.token_file = Path(token_file)
        self.host = parsed.netloc
        self.ssl_context = ssl.create_default_context()
        if ca_file:
            self.ssl_context.verify_flags |= ssl.VERIFY_X509_PARTIAL_CHAIN
            self.ssl_context.load_verify_locations(ca_file)
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=self.ssl_context),
            _NoRedirect(),
        )

    def token(self):
        if not self.token_file.is_file():
            raise JobRejected("Token do agente ausente.")
        value = self.token_file.read_text(encoding="utf-8").strip()
        if not value:
            raise JobRejected("Token do agente ausente.")
        return value

    def request(self, method, path, body=None, lease="", content_type="application/json"):
        data = body if isinstance(body, bytes) or body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header("Authorization", "Bearer " + self.token())
        if lease:
            req.add_header("X-Build-Lease", lease)
        if data is not None and content_type:
            req.add_header("Content-Type", content_type)
        try:
            with self.opener.open(req, timeout=60) as response:
                payload = response.read()
                if response.status == 204 or not payload:
                    return response.status, None
                if content_type == "application/json" or response.headers.get("Content-Type", "").startswith("application/json"):
                    return response.status, json.loads(payload.decode("utf-8"))
                return response.status, payload
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise JobFailed(f"Coordenador respondeu HTTP {exc.code}. {detail}") from exc

    def claim(self):
        status, payload = self.request("POST", "/builds/claim", {})
        if status == 204 or payload is None:
            return None
        return validate_job(payload)

    def heartbeat(self, job):
        self.request("POST", f"/builds/{job['id']}/heartbeat", {}, lease=job["lease_token"])

    def upload(self, job, ipa_path):
        payload = ipa_path.read_bytes()
        self.request(
            "PUT",
            f"/builds/{job['id']}/artifact",
            payload,
            lease=job["lease_token"],
            content_type="application/octet-stream",
        )

    def complete(self, job, resolved, status_name, tail):
        self.request(
            "POST",
            f"/builds/{job['id']}/complete",
            {"resolved_sha": resolved, "ipa_status": status_name, "log_tail": tail[-MAX_LOG:]},
            lease=job["lease_token"],
        )

    def fail(self, job, error, status_name, tail):
        self.request(
            "POST",
            f"/builds/{job['id']}/fail",
            {"error": error[:2000], "ipa_status": status_name, "log_tail": tail[-MAX_LOG:]},
            lease=job["lease_token"],
        )


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def run_scripts(job, workspace, scripts, env, deadline, lost):
    log_path = workspace / "build.log"
    for script in scripts:
        if lost.is_set():
            raise JobFailed("O lease do build expirou durante a compilação.")
        if time.monotonic() > deadline:
            raise JobFailed("O build excedeu o tempo limite de 2 horas.")
        print(f"Executando {script.name}.", flush=True)
        with log_path.open("ab") as log:
            log.write(f"\n# {script.name}\n".encode("utf-8"))
            proc = subprocess.Popen(
                ["/bin/bash", str(script)],
                cwd=str(workspace),
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            while proc.poll() is None:
                if lost.is_set() or time.monotonic() > deadline:
                    proc.terminate()
                    try:
                        proc.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=20)
                    if lost.is_set():
                        raise JobFailed("O lease do build expirou durante a compilação.")
                    raise JobFailed("O build excedeu o tempo limite de 2 horas.")
                time.sleep(2)
        if proc.returncode != 0:
            raise JobFailed(f"{script.name} terminou com status {proc.returncode}.")


def execute(job, config, client):
    workspace = Path(config["work_root"]) / job["id"]
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)
    scripts = script_list(config["script_dir"])
    env = build_env(job, workspace, config["path"])
    lost = threading.Event()
    stop = threading.Event()

    def beat():
        while not stop.wait(config["heartbeat_interval"]):
            try:
                client.heartbeat(job)
            except JobFailed as exc:
                print(str(exc), flush=True)
                lost.set()
                return

    thread = threading.Thread(target=beat, name="macos-build-heartbeat")
    thread.start()
    try:
        run_scripts(job, workspace, scripts, env, time.monotonic() + config["job_timeout"], lost)
        ipa = workspace / "output" / "app.ipa"
        status_name = ipa_status(workspace)
        tail = log_tail(workspace / "build.log")
        if not ipa.is_file() or ipa.read_bytes()[:2] != b"PK":
            detail = status_name or "nenhum IPA"
            raise JobFailed(f"O Mac não produziu um IPA ({detail}).", status_name)
        client.upload(job, ipa)
        client.complete(job, resolved_sha(workspace), status_name or "exported", tail)
        print(f"Build {job['id']} concluído.", flush=True)
    except JobFailed:
        raise
    finally:
        stop.set()
        thread.join(timeout=5)
        source = workspace / "source"
        if source.exists():
            shutil.rmtree(source, ignore_errors=True)


def load_config(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    required = ("coordinator_url", "token_file", "script_dir", "work_root", "path")
    missing = [key for key in required if not data.get(key)]
    if missing:
        raise JobRejected("Configuração incompleta: " + ", ".join(missing))
    data.setdefault("ca_file", "")
    data["poll_interval"] = int(data.get("poll_interval", 15))
    data["heartbeat_interval"] = int(data.get("heartbeat_interval", 30))
    data["job_timeout"] = int(data.get("job_timeout", 7200))
    return data


def fail_quietly(client, job, error, workspace):
    try:
        client.fail(job, error, ipa_status(workspace) if workspace else "", log_tail(workspace / "build.log") if workspace else "")
    except Exception as exc:
        print(f"Não foi possível registrar a falha: {exc}", flush=True)


def main(config_path):
    config = load_config(config_path)
    client = CoordinatorClient(config["coordinator_url"], config["token_file"], config.get("ca_file", ""))
    print("Agente iOS consultando " + client.host, flush=True)
    while True:
        job = None
        workspace = None
        try:
            job = client.claim()
            if job is None:
                time.sleep(config["poll_interval"])
                continue
            workspace = Path(config["work_root"]) / job["id"]
            print(f"Build {job['id']} reservado para {job['source_revision']}.", flush=True)
            execute(job, config, client)
        except JobRejected as exc:
            print(str(exc), flush=True)
            if job is not None:
                fail_quietly(client, job, str(exc), workspace)
            time.sleep(config["poll_interval"])
        except JobFailed as exc:
            print(str(exc), flush=True)
            if job is not None:
                fail_quietly(client, job, str(exc), workspace if workspace and workspace.exists() else None)
            else:
                time.sleep(config["poll_interval"])
        except Exception as exc:
            print(f"Falha inesperada: {exc}", flush=True)
            if job is not None:
                fail_quietly(client, job, "Falha inesperada no agente.", workspace if workspace and workspace.exists() else None)
            time.sleep(config["poll_interval"])


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: agent.py config.json", file=sys.stderr)
        sys.exit(2)
    try:
        main(sys.argv[1])
    except JobRejected as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
