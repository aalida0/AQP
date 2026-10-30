#!/usr/bin/env python3
"""Mock-only regression tests for the MG Condor backend static preflight."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

P = Path(__file__).resolve().parents[1] / "scripts/aqp_condor_backend_audit.py"
spec = importlib.util.spec_from_file_location("aqp_condor_backend_audit", P)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
import ast


def fun(body):
    return next(x for x in ast.parse(body).body if isinstance(x, ast.FunctionDef))


class ControllerAuditTests(unittest.TestCase):
    def test_pre_wait_status_read_detected(self):
        node = fun("""def control(self):
    status = subprocess.Popen(['condor_q'])
    error = status.stderr.read()
    if status.returncode:
        raise RuntimeError(error)
""")
        self.assertEqual(mod.find_unreaped_returncodes(node), [4])

    def test_post_wait_status_read_not_flagged(self):
        node = fun("""def control(self):
    status = subprocess.Popen(['condor_q'])
    stdout, stderr = status.communicate()
    if status.returncode:
        raise RuntimeError(stderr)
""")
        self.assertEqual(mod.find_unreaped_returncodes(node), [])

    def test_poll_after_read_does_not_fix_earlier_check(self):
        node = fun("""def control(self):
    status = subprocess.Popen(['condor_q'])
    if status.returncode:
        raise RuntimeError()
    status.poll()
""")
        self.assertEqual(mod.find_unreaped_returncodes(node), [3])

    def test_generic_submit_retry_is_detected(self):
        node = fun("""@multiple_try()
def submit(self):
    return condor_submit()
""")
        self.assertTrue(mod.has_retry(node))

    def test_no_submit_retry_is_not_detected(self):
        node = fun("""def submit(self):
    return condor_submit()
""")
        self.assertFalse(mod.has_retry(node))

    def test_actual_popen_nonzero_code_requires_poll_or_wait(self):
        with subprocess.Popen(
            ["bash", "-c", "printf 'SECMAN:2007\\n' >&2; exit 42"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        ) as process:
            stderr = process.stderr.read()
            stdout = process.stdout.read()
            self.assertIn(b"SECMAN:2007", stderr)
            self.assertEqual(stdout, b"")
            self.assertIsNone(process.returncode)  # Stored code is not yet reaped.
            self.assertEqual(process.wait(), 42)

    def test_detects_source_pattern_in_mock_install(self):
        cluster = """class Cluster:
    def check_termination(self, id): pass

class CondorCluster(Cluster):
    @multiple_try()
    def submit(self): pass

    @multiple_try()
    def submit2(self): pass

    @multiple_try(nb_try=10)
    def control(self):
        status = subprocess.Popen(['condor_q'])
        err = status.stderr.read()
        if status.returncode: raise RuntimeError(err)

    def control_one_job(self, id):
        status = subprocess.Popen(['condor_q'])
        err = status.stderr.read()
        if status.returncode: raise RuntimeError(err)
"""
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            one, two = base / "cluster.py", base / "misc.py"
            one.write_text(cluster)
            two.write_text("def Popen(*args, **kwargs): pass\n")
            result = mod.audit(one, two)
            flagged = {(severity, function) for severity, function, _ in result}
            self.assertIn(("RISK", "control"), flagged)
            self.assertIn(("RISK", "control_one_job"), flagged)
            self.assertIn(("RISK", "submit"), flagged)
            self.assertIn(("RISK", "submit2"), flagged)


if __name__ == "__main__":
    unittest.main()
