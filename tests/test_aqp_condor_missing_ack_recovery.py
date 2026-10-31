#!/usr/bin/env python3
"""Recovery of ambiguous Condor submit ACK in an isolated fake scheduler.

No live HTCondor, no physics worker, no production mutation or resubmission.
"""
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


class MissingAckRecoveryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        pack = self.root / "internal"
        pack.mkdir()
        (pack / "__init__.py").touch()
        for name in ("aqp_condor_intent_ledger.py", "aqp_condor_submission_guard.py",
                     "aqp_condor_completion_guard.py", "aqp_condor_missing_ack_recovery.py"):
            (pack / name).write_bytes((SCRIPTS / name).read_bytes())
        sys.path.insert(0, str(self.root))
        self.addCleanup(lambda: sys.path.remove(str(self.root)))
        self.addCleanup(self._clear_modules)
        self.guard = importlib.import_module("internal.aqp_condor_submission_guard")
        self.recovery = importlib.import_module("internal.aqp_condor_missing_ack_recovery")
        self.work = self.root / "P0_test"
        self.work.mkdir()
        self.args = ["27", "F", "0", "1"]
        self.outputs = ["GF27/results.dat", "GF27/log_MINT1.txt"]
        self.env = patch.dict(os.environ, {"AQP_CONDOR_INTENT_ROOT": str(self.root)})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.token = self.guard.reserve(
            str(self.work / "ajob1"), self.args, str(self.work), self.outputs)
        self.calls = []
        self.q = "910001 0 %s 2\n" % self.token
        self.h = ""

    @staticmethod
    def _clear_modules():
        for mod in list(sys.modules):
            if mod == "internal" or mod.startswith("internal."):
                del sys.modules[mod]

    def runner(self, cmd, **kwargs):
        self.calls.append(cmd)
        if cmd[0] == "condor_q":
            return SimpleNamespace(returncode=0, stdout=self.q, stderr="")
        return SimpleNamespace(returncode=0, stdout=self.h, stderr="")

    def test_read_only_discovery(self):
        result = self.recovery.recover(self.root, self.token, runner=self.runner)
        self.assertEqual(result["cluster_id"], "910001")
        self.assertFalse(result["acknowledged"])
        self.assertFalse(result["automatic_resubmission_allowed"])
        self.assertFalse(list(self.root.glob("ack_*.json")))
        self.assertTrue(all("-constraint" in x for x in self.calls))

    def test_recover_valid_queue_ack_without_resubmit(self):
        result = self.recovery.recover(
            self.root, self.token, runner=self.runner, commit=True)
        self.assertTrue(result["acknowledged"])
        ack = json.loads(next(self.root.glob("ack_*.json")).read_text())
        self.assertEqual(ack["required_output"], self.outputs)
        self.assertEqual(ack["cwd"], str(self.work))
        self.assertEqual(ack["cluster_id"], "910001")
        self.assertTrue(all(x[0] != "condor_submit" for x in self.calls))

    def test_recover_terminal_history(self):
        self.q = ""
        self.h = "910001 0 %s 4 0\n" % self.token
        result = self.recovery.recover(self.root, self.token, runner=self.runner)
        self.assertEqual(result["recovered_from"], "history")

    def test_failed_job_is_identified_but_never_resubmitted(self):
        self.q = ""
        self.h = "910001 0 %s 4 2\n" % self.token
        result = self.recovery.recover(self.root, self.token, runner=self.runner)
        self.assertFalse(result["automatic_resubmission_allowed"])

    def test_empty_queue_and_history_remains_blocked(self):
        self.q = ""
        with self.assertRaisesRegex(self.recovery.RecoveryBlocked, "Missing/duplicate"):
            self.recovery.recover(self.root, self.token, runner=self.runner)
        self.assertFalse(list(self.root.glob("ack_*.json")))

    def test_two_jobs_same_request_are_blocked(self):
        self.q += "910002 0 %s 2\n" % self.token
        with self.assertRaisesRegex(self.recovery.RecoveryBlocked, "Missing/duplicate"):
            self.recovery.recover(self.root, self.token, runner=self.runner, commit=True)

    def test_mismatched_request_is_blocked(self):
        self.q = "910001 0 WRONG_TOKEN 2\n"
        with self.assertRaisesRegex(self.recovery.RecoveryBlocked, "Foreign"):
            self.recovery.recover(self.root, self.token, runner=self.runner)

    def test_malformed_queue_is_blocked(self):
        self.q = "910001 0 2\n"
        with self.assertRaisesRegex(self.recovery.RecoveryBlocked, "Malformed"):
            self.recovery.recover(self.root, self.token, runner=self.runner)

    def test_active_and_history_conflict_are_blocked(self):
        self.h = "910001 0 %s 4 0\n" % self.token
        with self.assertRaisesRegex(self.recovery.RecoveryBlocked, "conflicting"):
            self.recovery.recover(self.root, self.token, runner=self.runner)

    def test_scheduler_query_error_remains_blocked(self):
        def error_runner(*args, **kwargs):
            return SimpleNamespace(returncode=42, stdout="", stderr="failed")
        with self.assertRaisesRegex(self.recovery.RecoveryBlocked, "query failed"):
            self.recovery.recover(self.root, self.token, runner=error_runner)

    def test_no_retry_after_restart(self):
        importlib.reload(self.recovery)
        with self.assertRaisesRegex(Exception, "Existing GF submission intent"):
            self.guard.reserve(str(self.work / "ajob1"), self.args, str(self.work),
                               self.outputs)
        self.assertFalse(list(self.root.glob("ack_*.json")))

    def test_legacy_intent_without_context_cannot_recover(self):
        intent = next(x for x in self.root.glob("*.json") if len(x.stem) == 64)
        data = json.loads(intent.read_text())
        del data["pre_submit_context"]
        intent.write_text(json.dumps(data))
        with self.assertRaisesRegex(self.recovery.RecoveryBlocked, "predates"):
            self.recovery.recover(self.root, self.token, runner=self.runner)

    def test_corrupt_intent_context_is_blocked(self):
        intent = next(x for x in self.root.glob("*.json") if len(x.stem) == 64)
        data = json.loads(intent.read_text())
        data["pre_submit_context"]["argument"][1] = "X"
        intent.write_text(json.dumps(data))
        with self.assertRaisesRegex(self.recovery.RecoveryBlocked, "Invalid durable"):
            self.recovery.recover(self.root, self.token, runner=self.runner)

    def test_preexisting_ack_never_overwritten(self):
        self.guard.acknowledge(self.token, "910001", str(self.work), self.outputs)
        before = next(self.root.glob("ack_*.json")).read_bytes()
        with self.assertRaisesRegex(self.recovery.RecoveryBlocked, "already exists"):
            self.recovery.recover(self.root, self.token, runner=self.runner, commit=True)
        self.assertEqual(next(self.root.glob("ack_*.json")).read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
