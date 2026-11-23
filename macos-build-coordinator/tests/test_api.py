import os
import tempfile
import unittest

from fastapi.testclient import TestClient

os.environ["TEKTON_TOKEN"] = "tekton-test-token"
os.environ["AGENT_TOKEN"] = "agent-test-token"
os.environ["LEASE_SECONDS"] = "180"
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="prodemge-coordinator-")

from app.main import app  # noqa: E402


def tekton(client):
    return {"Authorization": "Bearer tekton-test-token"}


def agent(client, lease=""):
    headers = {"Authorization": "Bearer agent-test-token"}
    if lease:
        headers["X-Build-Lease"] = lease
    return headers


class CoordinatorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["DATA_DIR"] = self.tmp.name
        os.environ["LEASE_SECONDS"] = "180"
        self.client = TestClient(app)
        self.client.__enter__()
        self.payload = {
            "build_request_id": "ios-one-ios-qa6sd8",
            "source_url": "https://github.com/raphaelmorsch/lab-devhub-prodemge.git",
            "source_revision": "main",
            "source_subdirectory": "sidsmobile-rn-0.87.1",
            "react_native_version": "rn-0.87.1",
            "script_set": "ios-build-v1",
        }

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.tmp.cleanup()

    def create(self, **overrides):
        body = dict(self.payload)
        body.update(overrides)
        return self.client.post("/builds", headers=tekton(self.client), json=body)

    def test_health_is_open(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)

    def test_roles_are_separate(self):
        created = self.create()
        self.assertEqual(created.status_code, 201)
        build_id = created.json()["id"]
        self.assertEqual(self.client.post("/builds/claim", headers=tekton(self.client)).status_code, 401)
        self.assertEqual(self.client.get(f"/builds/{build_id}", headers=agent(self.client)).status_code, 401)
        self.assertEqual(self.client.post("/builds", headers=agent(self.client), json=self.payload).status_code, 401)

    def test_rejects_shell_and_unknown_script(self):
        self.assertEqual(self.create(script_set="ios-build-v1; rm -rf /").status_code, 400)
        self.assertEqual(self.create(react_native_version="rn-0.68.7").status_code, 400)
        self.assertEqual(self.create(source_url="https://example.com/repo.git;touch /tmp/x").status_code, 400)
        self.assertEqual(self.create(source_revision="--upload-pack=evil").status_code, 400)
        self.assertEqual(self.create(source_subdirectory="../etc").status_code, 400)
        extra = dict(self.payload)
        extra["command"] = "bash -c id"
        response = self.client.post("/builds", headers=tekton(self.client), json=extra)
        self.assertEqual(response.status_code, 422)

    def test_claim_upload_and_download(self):
        created = self.create()
        build_id = created.json()["id"]
        claimed = self.client.post("/builds/claim", headers=agent(self.client))
        self.assertEqual(claimed.status_code, 200)
        lease = claimed.json()["lease_token"]
        self.assertNotIn("lease_token", self.client.get(f"/builds/{build_id}", headers=tekton(self.client)).json())
        busy = self.client.post("/builds/claim", headers=agent(self.client))
        self.assertEqual(busy.status_code, 204)
        heartbeat = self.client.post(
            f"/builds/{build_id}/heartbeat",
            headers=agent(self.client, lease),
        )
        self.assertEqual(heartbeat.status_code, 200)
        early = self.client.post(
            f"/builds/{build_id}/complete",
            headers=agent(self.client, lease),
            json={"resolved_sha": "06755832c00d046a6540c27b6ac9b93327ab9d2f", "ipa_status": "exported", "log_tail": "ok"},
        )
        self.assertEqual(early.status_code, 409)
        uploaded = self.client.put(
            f"/builds/{build_id}/artifact",
            headers=agent(self.client, lease),
            content=b"PK\x03\x04ipa",
        )
        self.assertEqual(uploaded.status_code, 200)
        done = self.client.post(
            f"/builds/{build_id}/complete",
            headers=agent(self.client, lease),
            json={"resolved_sha": "06755832c00d046a6540c27b6ac9b93327ab9d2f", "ipa_status": "exported", "log_tail": "ok"},
        )
        self.assertEqual(done.status_code, 200)
        self.assertEqual(done.json()["status"], "succeeded")
        downloaded = self.client.get(f"/builds/{build_id}/artifact", headers=tekton(self.client))
        self.assertEqual(downloaded.status_code, 200)
        self.assertEqual(downloaded.content, b"PK\x03\x04ipa")
        self.assertEqual(self.client.get(f"/builds/{build_id}/artifact", headers=agent(self.client)).status_code, 401)

    def test_failed_request_can_be_requeued(self):
        created = self.create(build_request_id="ios-retry")
        build_id = created.json()["id"]
        claimed = self.client.post("/builds/claim", headers=agent(self.client))
        lease = claimed.json()["lease_token"]
        failed = self.client.post(
            f"/builds/{build_id}/fail",
            headers=agent(self.client, lease),
            json={"error": "sandbox", "ipa_status": "archive-failed", "log_tail": "BUILD FAILED"},
        )
        self.assertEqual(failed.status_code, 200)
        again = self.create(build_request_id="ios-retry")
        self.assertEqual(again.status_code, 200)
        self.assertEqual(again.json()["id"], build_id)
        self.assertEqual(again.json()["status"], "queued")

    def test_agent_streams_the_build_log(self):
        created = self.create(build_request_id="ios-log")
        build_id = created.json()["id"]
        claimed = self.client.post("/builds/claim", headers=agent(self.client))
        lease = claimed.json()["lease_token"]
        first = self.client.post(
            f"/builds/{build_id}/log",
            headers=agent(self.client, lease),
            content=b"checkout ok\n",
        )
        self.assertEqual(first.status_code, 200)
        second = self.client.post(
            f"/builds/{build_id}/log",
            headers=agent(self.client, lease),
            content="archive ok\n".encode(),
        )
        self.assertEqual(second.status_code, 200)
        denied = self.client.get(f"/builds/{build_id}/log", headers=agent(self.client, lease))
        self.assertEqual(denied.status_code, 401)
        opened = self.client.get(f"/builds/{build_id}/log?offset=12", headers=tekton(self.client))
        self.assertEqual(opened.status_code, 200)
        self.assertEqual(opened.text, "archive ok\n")
        self.assertEqual(opened.headers["x-log-size"], str(second.json()["bytes"]))
        self.assertEqual(opened.headers["x-log-reset"], "0")
        status = self.client.get(f"/builds/{build_id}", headers=tekton(self.client))
        self.assertIn("archive ok", status.json()["log_tail"])
        self.client.post(
            f"/builds/{build_id}/fail",
            headers=agent(self.client, lease),
            json={"error": "sandbox", "ipa_status": "archive-failed", "log_tail": "archive ok"},
        )
        again = self.create(build_request_id="ios-log")
        self.assertEqual(again.json()["status"], "queued")
        cleared = self.client.post("/builds/claim", headers=agent(self.client))
        self.assertEqual(cleared.status_code, 200)
        empty = self.client.get(f"/builds/{build_id}/log", headers=tekton(self.client))
        self.assertEqual(empty.status_code, 200)
        self.assertEqual(empty.content, b"")

    def test_expired_lease_fails_the_build(self):
        os.environ["LEASE_SECONDS"] = "-1"
        try:
            created = self.create(build_request_id="ios-expire")
            build_id = created.json()["id"]
            claimed = self.client.post("/builds/claim", headers=agent(self.client))
            self.assertEqual(claimed.status_code, 200)
            lease = claimed.json()["lease_token"]
            status = self.client.get(f"/builds/{build_id}", headers=tekton(self.client))
            self.assertEqual(status.json()["status"], "failed")
            self.assertIn("lease", status.json()["error"])
            heartbeat = self.client.post(
                f"/builds/{build_id}/heartbeat",
                headers=agent(self.client, lease),
            )
            self.assertEqual(heartbeat.status_code, 409)
        finally:
            os.environ["LEASE_SECONDS"] = "180"


if __name__ == "__main__":
    unittest.main()
