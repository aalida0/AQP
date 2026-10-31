#!/usr/bin/env python3
"""Offline tests for fail-closed GF output completion gate and source patcher."""
import importlib
import hashlib
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from aqp_prepare_condor_output_gate import patch_text

FIXTURE = """import sys
class Cluster:
    def check_termination(self, job_id):
        return 'done'
class CondorCluster(Cluster):
    name = 'condor'
    job_id = 'CONDOR_ID'
    def control(self, me_dir):
        return None
"""

class OutputGateTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        package = self.root / "internal"
        package.mkdir()
        (package / "__init__.py").touch()
        for name in ("aqp_condor_intent_ledger.py",
                     "aqp_condor_submission_guard.py",
                     "aqp_condor_completion_guard.py",
                     "aqp_condor_output_manifest.py",
                     "aqp_condor_output_guard.py"):
            (package / name).write_bytes((SCRIPTS / name).read_bytes())
        sys.path.insert(0, str(self.root))
        self.addCleanup(lambda: sys.path.remove(str(self.root)))
        self.addCleanup(self.clear_modules)
        self.ledger = importlib.import_module("internal.aqp_condor_intent_ledger")
        self.submission = importlib.import_module("internal.aqp_condor_submission_guard")
        self.scheduler = importlib.import_module("internal.aqp_condor_completion_guard")
        self.manifest = importlib.import_module("internal.aqp_condor_output_manifest")
        self.guard = importlib.import_module("internal.aqp_condor_output_guard")
        self.cwd = self.root / "channel"
        self.cwd.mkdir()
        (self.cwd / "res_1.dat").write_bytes(b"mock integrated GF output\n")
        self.sha = hashlib.sha256(b"frozen card/source fixture").hexdigest()
        self.environment = patch.dict(os.environ, {
            "AQP_CONDOR_INTENT_ROOT": str(self.root),
            "AQP_CONDOR_INPUT_SHA256": self.sha,
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.token = self.submission.reserve(
            str(self.root / "ajob1"), ["GF7.0", "foo", "bar", "1"], str(self.cwd))
        self.submission.acknowledge(self.token, "910001")
        self.retry = {"cwd": str(self.cwd), "required_output": ["res_1.dat"]}

    @staticmethod
    def clear_modules():
        for name in list(sys.modules):
            if name == "internal" or name.startswith("internal."):
                del sys.modules[name]

    def publish(self):
        return self.manifest.publish(
            self.root, self.cwd,
            request_id=self.token, cluster_id="910001",
            input_sha256=self.sha, process=str(self.cwd),
            stage="MINT1", gf="GF7.0", required_output=["res_1.dat"])

    def checked(self):
        with patch.object(self.scheduler, "check", return_value="TERMINATED"):
            return self.guard.require_verified("910001", self.retry)

    def test_verified_output_passes(self):
        self.publish()
        self.assertTrue(self.checked())

    def test_missing_manifest_blocks_completion(self):
        with self.assertRaisesRegex(self.guard.CondorOutputError, "manifest invalid"):
            self.checked()

    def test_tampered_grid_blocks_completion(self):
        self.publish()
        (self.cwd / "res_1.dat").write_bytes(b"corrupted grid")
        with self.assertRaisesRegex(self.guard.CondorOutputError, "manifest invalid"):
            self.checked()

    def test_wrong_source_hash_blocks_completion(self):
        self.publish()
        os.environ["AQP_CONDOR_INPUT_SHA256"] = "f" * 64
        with self.assertRaisesRegex(self.guard.CondorOutputError, "manifest invalid"):
            self.checked()

    def test_wrong_job_id_blocks_completion(self):
        self.publish()
        with patch.object(self.scheduler, "check", return_value="TERMINATED"):
            with self.assertRaises(Exception):
                self.guard.require_verified("910002", self.retry)

    def test_active_scheduler_job_never_checks_grid(self):
        self.publish()
        with patch.object(self.scheduler, "check", return_value="ACTIVE"):
            with self.assertRaisesRegex(self.guard.CondorOutputError, "not been independently"):
                self.guard.require_verified("910001", self.retry)

    def test_no_required_output_blocks_completion(self):
        with self.assertRaisesRegex(self.guard.CondorOutputError, "cwd/required_output"):
            self.guard.require_verified("910001", {"cwd": str(self.cwd), "required_output": []})

    def test_missing_frozen_input_hash_blocks(self):
        self.publish()
        del os.environ["AQP_CONDOR_INPUT_SHA256"]
        with self.assertRaisesRegex(self.guard.CondorOutputError, "fingerprint"):
            self.guard.require_verified("910001", self.retry)

    def test_source_patch_injects_unique_override(self):
        source = patch_text(FIXTURE)
        self.assertEqual(source.count("_aqp_output_guard.require_verified("), 1)
        self.assertIn("super(CondorCluster, self).check_termination(job_id)", source)

    def test_source_patch_rejects_existing_override(self):
        changed = FIXTURE.replace(
            "    def control(self, me_dir):",
            "    def check_termination(self, job_id):\n        return True\n"
            "    def control(self, me_dir):")
        with self.assertRaisesRegex(ValueError, "already overrides"):
            patch_text(changed)

    def test_override_only_calls_mg_after_verified_manifest(self):
        source = patch_text(FIXTURE)
        env = {"ClusterManagmentError": RuntimeError}
        exec(source, env)
        controller = env["CondorCluster"]()
        controller.retry_args = {"910001": self.retry}
        with patch.object(self.guard, "require_verified",
                          side_effect=self.guard.CondorOutputError("unverified")):
            with self.assertRaises(self.guard.CondorOutputError):
                controller.check_termination("910001")
        with patch.object(self.guard, "require_verified", return_value=True) as verified:
            self.assertEqual(controller.check_termination("910001"), "done")
            verified.assert_called_once_with("910001", self.retry)

    def test_missing_retry_provenance_blocks_base_completion(self):
        source = patch_text(FIXTURE)
        env = {"ClusterManagmentError": RuntimeError}
        exec(source, env)
        controller = env["CondorCluster"]()
        controller.retry_args = {}
        with self.assertRaisesRegex(RuntimeError, "Missing GF retry provenance"):
            controller.check_termination("910001")


if __name__ == "__main__":
    unittest.main()
