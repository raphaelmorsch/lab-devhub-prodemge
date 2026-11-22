import hmac
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

ALLOWED_SCRIPT_SET = "ios-build-v1"
ALLOWED_RN = ("rn-0.87.1", "rn-0.88.1")
MAX_LOG = 65536


def data_dir():
    return Path(os.environ.get("DATA_DIR", "/data"))


def db_path():
    return data_dir() / "builds.db"


def lease_seconds():
    return int(os.environ.get("LEASE_SECONDS", "180"))


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def connect():
    data_dir().mkdir(parents=True, exist_ok=True)
    probe = data_dir() / ".write-test"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink()
    conn = sqlite3.connect(db_path(), timeout=5, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


@contextmanager
def session():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with session() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS builds (
                id TEXT PRIMARY KEY,
                build_request_id TEXT NOT NULL UNIQUE,
                source_url TEXT NOT NULL,
                source_revision TEXT NOT NULL,
                source_subdirectory TEXT NOT NULL,
                react_native_version TEXT NOT NULL,
                script_set TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                lease_until REAL,
                lease_token TEXT NOT NULL DEFAULT '',
                resolved_sha TEXT NOT NULL DEFAULT '',
                ipa_status TEXT NOT NULL DEFAULT '',
                error TEXT NOT NULL DEFAULT '',
                log_tail TEXT NOT NULL DEFAULT '',
                artifact_ready INTEGER NOT NULL DEFAULT 0
            )
            """
        )


def artifact_path(build_id):
    return data_dir() / "artifacts" / build_id / "app.ipa"


def trim_log(value):
    text = (value or "").replace("\x00", "")
    if len(text) > MAX_LOG:
        return text[-MAX_LOG:]
    return text


def expire_leases(conn):
    now = time.time()
    conn.execute(
        """
        UPDATE builds
        SET status = 'failed',
            error = 'O agente não renovou o lease.',
            lease_token = '',
            lease_until = NULL,
            updated_at = ?
        WHERE status = 'running'
          AND lease_until IS NOT NULL
          AND lease_until < ?
        """,
        (now_iso(), now),
    )


def public_row(row):
    return {
        "id": row["id"],
        "build_request_id": row["build_request_id"],
        "status": row["status"],
        "source_url": row["source_url"],
        "source_revision": row["source_revision"],
        "source_subdirectory": row["source_subdirectory"],
        "react_native_version": row["react_native_version"],
        "script_set": row["script_set"],
        "resolved_sha": row["resolved_sha"],
        "ipa_status": row["ipa_status"],
        "error": row["error"],
        "log_tail": row["log_tail"],
        "artifact_ready": bool(row["artifact_ready"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def claim_row(row):
    payload = public_row(row)
    payload["lease_token"] = row["lease_token"]
    return payload


def same_request(row, fields):
    return (
        row["source_url"] == fields["source_url"]
        and row["source_revision"] == fields["source_revision"]
        and row["source_subdirectory"] == fields["source_subdirectory"]
        and row["react_native_version"] == fields["react_native_version"]
        and row["script_set"] == fields["script_set"]
    )


def create_build(fields):
    with session() as conn:
        expire_leases(conn)
        existing = conn.execute(
            "SELECT * FROM builds WHERE build_request_id = ?",
            (fields["build_request_id"],),
        ).fetchone()
        if existing is not None:
            if not same_request(existing, fields):
                return "conflict", public_row(existing)
            if existing["status"] == "failed":
                artifact = artifact_path(existing["id"])
                if artifact.exists():
                    artifact.unlink()
                conn.execute(
                    """
                    UPDATE builds
                    SET status = 'queued',
                        error = '',
                        log_tail = '',
                        ipa_status = '',
                        resolved_sha = '',
                        artifact_ready = 0,
                        lease_token = '',
                        lease_until = NULL,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (now_iso(), existing["id"]),
                )
                existing = conn.execute(
                    "SELECT * FROM builds WHERE id = ?",
                    (existing["id"],),
                ).fetchone()
                return "requeued", public_row(existing)
            return "exists", public_row(existing)
        build_id = str(uuid.uuid4())
        stamp = now_iso()
        conn.execute(
            """
            INSERT INTO builds (
                id, build_request_id, source_url, source_revision,
                source_subdirectory, react_native_version, script_set,
                status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'queued', ?, ?)
            """,
            (
                build_id,
                fields["build_request_id"],
                fields["source_url"],
                fields["source_revision"],
                fields["source_subdirectory"],
                fields["react_native_version"],
                fields["script_set"],
                stamp,
                stamp,
            ),
        )
        row = conn.execute("SELECT * FROM builds WHERE id = ?", (build_id,)).fetchone()
        return "created", public_row(row)


def get_build(build_id):
    with session() as conn:
        expire_leases(conn)
        row = conn.execute("SELECT * FROM builds WHERE id = ?", (build_id,)).fetchone()
        if row is None:
            return None
        return public_row(row)


def claim_job():
    with session() as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            expire_leases(conn)
            running = conn.execute(
                "SELECT id FROM builds WHERE status = 'running'"
            ).fetchone()
            if running is not None:
                conn.execute("COMMIT")
                return None
            row = conn.execute(
                """
                SELECT * FROM builds
                WHERE status = 'queued'
                ORDER BY created_at, id
                LIMIT 1
                """
            ).fetchone()
            if row is None:
                conn.execute("COMMIT")
                return None
            token = str(uuid.uuid4())
            until = time.time() + lease_seconds()
            conn.execute(
                """
                UPDATE builds
                SET status = 'running',
                    lease_token = ?,
                    lease_until = ?,
                    error = '',
                    updated_at = ?
                WHERE id = ? AND status = 'queued'
                """,
                (token, until, now_iso(), row["id"]),
            )
            updated = conn.execute(
                "SELECT * FROM builds WHERE id = ?",
                (row["id"],),
            ).fetchone()
            conn.execute("COMMIT")
            return claim_row(updated)
        except Exception:
            conn.execute("ROLLBACK")
            raise


def running_with_lease(conn, build_id, lease):
    row = conn.execute("SELECT * FROM builds WHERE id = ?", (build_id,)).fetchone()
    if row is None:
        return None, "missing"
    if row["status"] != "running" or not row["lease_token"] or not hmac.compare_digest(row["lease_token"], lease):
        return row, "lease"
    if row["lease_until"] is None or row["lease_until"] < time.time():
        return row, "lease"
    return row, "ok"


def heartbeat(build_id, lease):
    with session() as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            expire_leases(conn)
            row, state = running_with_lease(conn, build_id, lease)
            if state != "ok":
                conn.execute("COMMIT")
                return state
            until = time.time() + lease_seconds()
            conn.execute(
                """
                UPDATE builds
                SET lease_until = ?, updated_at = ?
                WHERE id = ?
                """,
                (until, now_iso(), build_id),
            )
            conn.execute("COMMIT")
            return "ok"
        except Exception:
            conn.execute("ROLLBACK")
            raise


def save_artifact(build_id, lease, payload):
    with session() as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            expire_leases(conn)
            row, state = running_with_lease(conn, build_id, lease)
            if state != "ok":
                conn.execute("COMMIT")
                return state
            path = artifact_path(build_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".ipa.partial")
            temporary.write_bytes(payload)
            temporary.replace(path)
            conn.execute(
                """
                UPDATE builds
                SET artifact_ready = 1, updated_at = ?
                WHERE id = ?
                """,
                (now_iso(), build_id),
            )
            conn.execute("COMMIT")
            return "ok"
        except Exception:
            conn.execute("ROLLBACK")
            raise


def finish(build_id, lease, status, error, resolved_sha, ipa_status, log_tail):
    with session() as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            expire_leases(conn)
            row, state = running_with_lease(conn, build_id, lease)
            if state != "ok":
                conn.execute("COMMIT")
                return state, None
            if status == "succeeded" and not row["artifact_ready"]:
                conn.execute("COMMIT")
                return "no-artifact", None
            conn.execute(
                """
                UPDATE builds
                SET status = ?,
                    error = ?,
                    resolved_sha = ?,
                    ipa_status = ?,
                    log_tail = ?,
                    lease_token = '',
                    lease_until = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    error,
                    resolved_sha,
                    ipa_status,
                    trim_log(log_tail),
                    now_iso(),
                    build_id,
                ),
            )
            updated = conn.execute(
                "SELECT * FROM builds WHERE id = ?",
                (build_id,),
            ).fetchone()
            conn.execute("COMMIT")
            return "ok", public_row(updated)
        except Exception:
            conn.execute("ROLLBACK")
            raise
