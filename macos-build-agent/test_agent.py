import tempfile
import unittest
from pathlib import Path

import agent


class AgentContractTest(unittest.TestCase):
    def job(self, **overrides):
        payload = {
            "id": "11111111-1111-1111-1111-111111111111",
            "lease_token": "22222222-2222-2222-2222-222222222222",
            "build_request_id": "ios-one-ios-qa6sd8",
            "source_url": "https://github.com/raphaelmorsch/lab-devhub-prodemge.git",
            "source_revision": "main",
            "source_subdirectory": "sidsmobile-rn-0.87.1",
            "react_native_version": "rn-0.87.1",
            "script_set": "ios-build-v1",
        }
        payload.update(overrides)
        return payload

    def test_accepts_the_fixed_contract(self):
        accepted = agent.validate_job(self.job())
        self.assertEqual(accepted["script_set"], "ios-build-v1")
        self.assertNotIn("command", accepted)

    def test_rejects_arbitrary_commands_and_bad_refs(self):
        with self.assertRaises(agent.JobRejected):
            agent.validate_job(self.job(script_set="custom", command="bash -c id"))
        with self.assertRaises(agent.JobRejected):
            agent.validate_job(self.job(react_native_version="rn-0.68.7"))
        with self.assertRaises(agent.JobRejected):
            agent.validate_job(self.job(source_url="https://example.com/app.git; id"))
        with self.assertRaises(agent.JobRejected):
            agent.validate_job(self.job(source_revision="-rf"))
        with self.assertRaises(agent.JobRejected):
            agent.validate_job(self.job(source_subdirectory="../../tmp"))

    def test_script_list_is_the_versioned_sequence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in agent.SCRIPTS:
                (root / name).write_text("#!/bin/bash\n", encoding="utf-8")
            paths = agent.script_list(root)
            self.assertEqual([path.name for path in paths], list(agent.SCRIPTS))
            (root / "extra.sh").write_text("#!/bin/bash\n", encoding="utf-8")
            self.assertEqual([path.name for path in agent.script_list(root)], list(agent.SCRIPTS))

    def test_environment_has_no_shell_injection_slot(self):
        job = agent.validate_job(self.job())
        env = agent.build_env(job, Path("/tmp/workspace"), "/usr/bin")
        self.assertNotIn("lease_token", env)
        self.assertEqual(env["SOURCE_SHA"], "main")
        self.assertEqual(env["CI_PROJECT_DIR"], "/tmp/workspace")


if __name__ == "__main__":
    unittest.main()
