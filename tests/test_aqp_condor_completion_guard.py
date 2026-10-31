#!/usr/bin/env python3
"""Offline tests for the UNDEPLOYED Condor queue/history status guard.

Tests the real decision function with a fake subprocess runner, and an
AST-modified representative controller class. Never calls actual HTCondor.
"""
import importlib
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from aqp_prepare_condor_status_gate import patch_text

SOURCE = '''import sys
class CondorCluster:
    def control_one_job(self, id):
        output = ''
        return output

    def control(self, me_dir):
        run = 0
        for id in self.submitted_ids:
            if id not in []:
                status = self.check_termination(id)
            elif status != 'C':
                run += 1
        return run
'''


class CompletionGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        package = self.root / "internal"
        package.mkdir()
        (package / "__init__.py").touch()
        for name in ("aqp_condor_submission_guard.py",
                     "aqp_condor_intent_ledger.py",
                     "aqp_condor_completion_guard.py"):
            (package / name).write_bytes((SCRIPTS / name).read_bytes())
        sys.path.insert(0, str(self.root))
        self.addCleanup(lambda: sys.path.remove(str(self.root)))
        self.addCleanup(self._clear_imports)
        self.ledger = importlib.import_module("internal.aqp_condor_intent_ledger")
        self.submission = importlib.import_module("internal.aqp_condor_submission_guard")
        self.guard = importlib.import_module("internal.aqp_condor_completion_guard")
        self.cwd = self.root / "P2_test"
        self.cwd.mkdir()
        self.prog = self.root / "ajob1"
        self.prog.touch()
        self.environment = patch.dict(os.environ,
                                      {"AQP_CONDOR_INTENT_ROOT": str(self.root)})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.token = self.submission.reserve(
            str(self.prog), ["GF7.0", "second", "third", "1"], str(self.cwd),
            ["G0/log_MINT1.txt", "G0/results.dat"])
        self.submission.acknowledge(
            self.token, "910001", str(self.cwd),
            ["G0/log_MINT1.txt", "G0/results.dat"])
        self.queries = []

    @staticmethod
    def _clear_imports():
        for name in list(sys.modules):
            if name == "internal" or name.startswith("internal."):
                del sys.modules[name]

    def fake_runner(self, active="", history="", rc=0):
        def run(cmd, **kwargs):
            self.queries.append(cmd)
            if cmd[0] == "condor_q":
                return SimpleNamespace(returncode=rc, stdout=active)
            return SimpleNamespace(returncode=rc, stdout=history)
        return run

    def test_queued_job_is_not_marked_complete(self):
        line = f"910001 0 2 {self.token}\n"
        self.assertEqual(self.guard.check(
            "910001", self.fake_runner(active=line)), "ACTIVE")
        self.assertEqual(len(self.queries), 1)


    def test_visible_completed_job_remains_outstanding(self):
        line = f"910001 0 4 {self.token}\n"
        self.assertEqual(self.guard.check(
            "910001", self.fake_runner(active=line)), "ACTIVE")

    def test_history_success_requires_matching_token_and_exit_zero(self):
        line = f"910001 0 4 0 {self.token}\n"
        self.assertEqual(self.guard.check(
            "910001", self.fake_runner(history=line)), "TERMINATED")
        self.assertEqual(len(self.queries), 2)

    def test_successful_empty_queue_without_history_fails_closed(self):
        with self.assertRaisesRegex(self.guard.CondorEvidenceError,
                                    "No unique terminal history"):
            self.guard.check("910001", self.fake_runner())

    def test_missing_or_wrong_classad_fails_closed(self):
        line = "910001 0 4 0 NOT_MY_REQUEST\n"
        with self.assertRaisesRegex(self.guard.CondorEvidenceError,
                                    "Terminal history not proven"):
            self.guard.check("910001", self.fake_runner(history=line))

    def test_scheduler_nonzero_exit_fails_closed(self):
        with self.assertRaisesRegex(self.guard.CondorEvidenceError,
                                    "Scheduler query failed"):
            self.guard.check("910001", self.fake_runner(rc=42))

    def test_nested_import_sys_does_not_shadow_module_anchor(self):
        source = SOURCE.replace(
            "    def control(self, me_dir):",
            "    def control(self, me_dir):\n        import sys", 1)
        candidate = patch_text(source)
        self.assertEqual(candidate.count(
            "from internal import aqp_condor_completion_guard as"), 1)
        compile(candidate, "status_with_nested_sys.py", "exec")

    def test_nested_import_sys_without_module_import_fails_closed(self):
        source = SOURCE.replace("import sys\nclass CondorCluster:",
                                "class CondorCluster:")
        source = source.replace(
            "    def control(self, me_dir):",
            "    def control(self, me_dir):\n        import sys", 1)
        with self.assertRaisesRegex(ValueError, "module-level import sys"):
            patch_text(source)

    def test_source_gate_injects_into_both_status_methods(self):
        source = patch_text(SOURCE)
        self.assertEqual(source.count("_aqp_completion_guard.check("), 3)
        self.assertIn("return 'C'", source)
        self.assertIn("    continue", source)

    def test_queue_visible_completed_job_is_not_counted_finished(self):
        # A source-compatible controller fragment: prior candidate returned
        # (idle=0, running=0, finished=1, failed=0) for queue-visible C.
        # The corrected candidate must keep it running until independently
        # verified terminal history and output checks can occur.
        source = """import sys
class CondorCluster:
    def control_one_job(self, id):
        output = ''
        return output

    def control(self, me_dir):
        idle, run, fail = 0, 0, 0
        ongoing = []
        for id in self.submitted_ids:
            status = 'C'
            ongoing.append(id)
            if status in ['I', 'U']:
                idle += 1
            elif status == 'R':
                run += 1
            elif status != 'C':
                fail += 1
        for id in list(self.submitted_ids):
            if id not in ongoing:
                status = self.check_termination(id)
        return idle, run, self.submitted - (idle + run + fail), fail
"""
        env = {"ClusterManagmentError": RuntimeError}
        exec(patch_text(source), env)
        controller = env["CondorCluster"]()
        controller.submitted_ids = ["910001"]
        controller.submitted = 1
        controller.check_termination = lambda _id: self.fail(
            "Early check_termination on queue-visible C")
        with patch.object(self.guard, "check", return_value="ACTIVE"):
            self.assertEqual(controller.control("."), (0, 1, 0, 0))

    def test_ambiguous_history_never_invokes_output_check(self):
        env = {"ClusterManagmentError": RuntimeError}
        exec(patch_text(SOURCE), env)
        controller = env["CondorCluster"]()
        controller.submitted_ids = ["910001"]
        def output_check(_):
            self.fail("Unsafe output-completion check on unresolved scheduler state")
        controller.check_termination = output_check
        with patch.object(self.guard, "check", side_effect=self.guard.CondorEvidenceError("UNKNOWN")):
            with self.assertRaises(self.guard.CondorEvidenceError):
                controller.control(".")

    def test_active_individual_job_is_preserved_as_running(self):
        env = {"ClusterManagmentError": RuntimeError}
        exec(patch_text(SOURCE), env)
        controller = env["CondorCluster"]()
        with patch.object(self.guard, "check", return_value="ACTIVE"):
            self.assertEqual(controller.control_one_job("910001"), "R")

    def test_finished_individual_job_yields_completed_status_only(self):
        env = {"ClusterManagmentError": RuntimeError}
        exec(patch_text(SOURCE), env)
        controller = env["CondorCluster"]()
        with patch.object(self.guard, "check", return_value="TERMINATED"):
            self.assertEqual(controller.control_one_job("910001"), "C")


if __name__ == "__main__":
    unittest.main()
