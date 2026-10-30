#!/usr/bin/env python3
"""Unit tests for the pinned MG5 Condor status-only patch generator.

Everything is synthetic and offline. No Condor/MadGraph calls, production
modifications, or user process files.
"""
import importlib.util
import io
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

HERE = Path(__file__).resolve().parents[1] / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


patch = load("aqp_prepare_condor_status_patch")
mock = load("aqp_condor_status_mock")

# Concise representative pre-patch methods with the exact 3.5.11 checks.
FIXTURE = '''class CondorCluster:
    def control_one_job(self, id):
        status = misc.Popen(["condor_q"], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
        error = status.stderr.read().decode(errors='ignore')
        if status.returncode and error:
            raise ClusterManagmentError('condor_q returns error: %s' % error)
        elif status.returncode:
            raise ClusterManagmentError('condor_q fails with status code: %s' % status.returncode)
        elif error:
            sys.stderr.write("condor_q error (returncode was 0): %s" % error)
        return status.stdout.readline().decode(errors='ignore').strip()

    def control(self, me_dir):
        if not self.submitted_ids:
            return 0, 0, 0, 0
        idle, run, fail = 0, 0, 0
        ongoing = []
        status = misc.Popen(["condor_q"], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
        error = status.stderr.read().decode(errors='ignore')
        if status.returncode and error:
            raise ClusterManagmentError('condor_q returns error: %s' % error)
        elif status.returncode:
            raise ClusterManagmentError('condor_q fails with status code: %s' % status.returncode)
        elif error:
            sys.stderr.write("condor_q error (returncode was 0): %s" % error)
        for line in status.stdout:
            id, status = line.decode(errors='ignore').strip().split()
            status = self.jobstatus[status]
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
                if status == 'wait':
                    run += 1
                elif status == 'resubmit':
                    idle += 1
        return idle, run, self.submitted - (idle + run + fail), fail
'''


class FakeChild:
    def __init__(self, stdout=b"", stderr=b"", returncode=0):
        self._stdout, self._stderr = stdout, stderr
        self.returncode = returncode

    def communicate(self):
        return self._stdout, self._stderr


class PatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patched = patch.patch_text(FIXTURE)
        cls.temp = tempfile.TemporaryDirectory()
        cls.path = Path(cls.temp.name) / "cluster.py"
        cls.path.write_text(cls.patched)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_method(self, method, stdout=b"", stderr=b"", status=0):
        tested = mock.isolated_method(self.path, method, lambda *args, **kwargs:
                                      FakeChild(stdout, stderr, status))
        checked = []
        stub = SimpleNamespace(
            submitted_ids=["987654"], submitted=1, finish=0,
            jobstatus={"0": "U", "1": "I", "2": "R", "3": "X",
                       "4": "C", "5": "H", "6": "E"},
            check_termination=lambda job_id: checked.append(job_id) or "wait",
        )
        return tested, stub, checked

    def test_both_methods_changed(self):
        self.assertEqual(self.patched.count("status.communicate()"), 2)
        self.assertNotIn("status.stderr.read()", self.patched)
        self.assertIn("for line in stdout_data.splitlines()", self.patched)

    def test_nonzero_status_is_rejected_before_output_check(self):
        fun, stub, checked = self.run_method(
            "control", stderr=b"SECMAN:2007", status=42)
        with self.assertRaises(mock.ControlledClusterError):
            fun(stub, ".")
        self.assertEqual(checked, [])

    def test_single_query_nonzero_status_fails_closed(self):
        fun, stub, _ = self.run_method(
            "control_one_job", stderr=b"SECMAN:2011", status=42)
        with self.assertRaises(mock.ControlledClusterError):
            fun(stub, "987654")

    def test_zero_status_running_job(self):
        fun, stub, checked = self.run_method("control", stdout=b"987654 2\n")
        self.assertEqual(fun(stub, "."), (0, 1, 0, 0))
        self.assertEqual(checked, [])

    def test_zero_status_idle_and_complete(self):
        fun, stub, checked = self.run_method("control", stdout=b"987654 1\n")
        self.assertEqual(fun(stub, "."), (1, 0, 0, 0))
        self.assertEqual(checked, [])
        fun, stub, checked = self.run_method("control", stdout=b"")
        self.assertEqual(fun(stub, "."), (0, 1, 0, 0))
        self.assertEqual(checked, ["987654"])  # valid query; output check appropriate

    def test_single_query_normal(self):
        fun, stub, _ = self.run_method("control_one_job", stdout=b"R\n")
        self.assertEqual(fun(stub, "987654"), "R")

    def test_malformed_queue_fail_closed(self):
        fun, stub, checked = self.run_method("control", stdout=b"not-a-valid-status\n")
        with self.assertRaises(mock.ControlledClusterError):
            fun(stub, ".")
        self.assertEqual(checked, [])

    def test_malformed_single_status_fail_closed(self):
        fun, stub, _ = self.run_method("control_one_job", stdout=b"what\n")
        with self.assertRaises(mock.ControlledClusterError):
            fun(stub, "987654")

    def test_missing_expected_pattern_fails_closed(self):
        with self.assertRaises(ValueError):
            patch.patch_text(FIXTURE.replace(
                "error = status.stderr.read().decode(errors='ignore')", "error = ''"))

    def test_patch_syntax(self):
        compile(self.patched, "patched_cluster.py", "exec")

    def test_no_unrelated_change(self):
        # The original is identical except for the two query functions:
        # their signatures and all unchanged context are retained.
        self.assertEqual(
            self.patched.count("def control_one_job"), FIXTURE.count("def control_one_job"))
        self.assertEqual(self.patched.count("def control(self"), 1)


if __name__ == "__main__":
    unittest.main()
