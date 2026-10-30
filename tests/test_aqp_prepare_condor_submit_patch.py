#!/usr/bin/env python3
"""Offline unit tests for fail-closed MG5 internal condor_submit candidate.

No MadGraph import, no real HTCondor commands, and no production artifacts.
"""
import importlib.util
from pathlib import Path
import unittest

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"


def load(script):
    spec = importlib.util.spec_from_file_location(script, SCRIPT_DIR / (script + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


patch = load("aqp_prepare_condor_submit_patch")
mock = load("aqp_condor_submit_mock")

FIXTURE = '''class CondorCluster:
    @multiple_try()
    def submit(self, prog, cwd=None):
        dico = {}
        text = "dummy"
        a = misc.Popen(['condor_submit'], stdout=subprocess.PIPE,
                       stdin=subprocess.PIPE)
        output, _ = a.communicate((text % dico).encode())
        pat = re.compile(r"submitted to cluster (\\d*)", re.MULTILINE)
        output = output.decode(errors='ignore')
        try:
            id = pat.search(output).groups()[0]
        except:
            raise ClusterManagmentError("ambiguous acknowledgement")
        self.submitted += 1
        self.submitted_ids.append(id)
        return id

    @store_input()
    @multiple_try()
    def submit2(self, prog, cwd=None, input_files=[]):
        dico = {}
        text = "dummy"
        a = subprocess.Popen(['condor_submit'], stdout=subprocess.PIPE,
                             stdin=subprocess.PIPE)
        output, _ = a.communicate((text % dico).encode())
        output = output.decode(errors='ignore')
        pat = re.compile(r"submitted to cluster (\\d*)", re.MULTILINE)
        try:
            id = pat.search(output).groups()[0]
        except:
            raise ClusterManagmentError("ambiguous acknowledgement")
        self.submitted += 1
        self.submitted_ids.append(id)
        return id
'''


class PatchSubmitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidate = patch.patch_text(FIXTURE)

    def test_status_and_append_paths_unchanged(self):
        self.assertEqual(self.candidate.count("self.submitted_ids.append(id)"), 2)
        self.assertEqual(self.candidate.count("@store_input()"), 1)
        self.assertNotIn("@multiple_try()", self.candidate)
        self.assertEqual(self.candidate.count("if a.returncode != 0:"), 2)

    def test_compiles_without_external_imports(self):
        compile(self.candidate, "fixture_cluster.py", "exec")

    def test_single_normal_submission(self):
        for method in ("submit", "submit2"):
            with self.subTest(method=method):
                result = mock.attempt(
                    method, self.candidate, None,
                    [(b"1 job(s) submitted to cluster 910001.\n", 0)],
                    candidate=True,
                )
                self.assertEqual(result["attempts"], 1)
                self.assertEqual(result["tracked_ids"], ["910001"])
                self.assertIsNone(result["error"])

    def test_ambiguous_ack_fails_without_resubmitting(self):
        for method in ("submit", "submit2"):
            with self.subTest(method=method):
                result = mock.attempt(
                    method, self.candidate, None,
                    [(b"Submitting job(s).\n", 0),
                     (b"1 job(s) submitted to cluster 910002.\n", 0)],
                    candidate=True,
                )
                self.assertEqual(result["attempts"], 1)
                self.assertEqual(result["tracked_ids"], [])
                self.assertIsNotNone(result["error"])

    def test_nonzero_exit_with_valid_id_still_fails(self):
        for method in ("submit", "submit2"):
            with self.subTest(method=method):
                result = mock.attempt(
                    method, self.candidate, None,
                    [(b"1 job(s) submitted to cluster 910001.\n", 42)],
                    candidate=True,
                )
                self.assertEqual(result["attempts"], 1)
                self.assertEqual(result["tracked_ids"], [])
                self.assertIn("exit 42", result["error"])

    def test_empty_numeric_capture_fails(self):
        for method in ("submit", "submit2"):
            with self.subTest(method=method):
                result = mock.attempt(
                    method, self.candidate, None,
                    [(b"submitted to cluster \n", 0)],
                    candidate=True,
                )
                self.assertEqual(result["attempts"], 1)
                self.assertEqual(result["tracked_ids"], [])
                self.assertIsNotNone(result["error"])

    def test_fail_if_retry_decorator_not_present(self):
        with self.assertRaises(ValueError):
            patch.patch_text(FIXTURE.replace("@multiple_try()", "", 1))

    def test_fail_if_upstream_submit_call_changes(self):
        with self.assertRaises(ValueError):
            patch.patch_text(FIXTURE.replace(
                "a = misc.Popen(['condor_submit'], stdout=subprocess.PIPE,",
                "a = subprocess.run(['condor_submit'], stdout=subprocess.PIPE,"
            ))


if __name__ == "__main__":
    unittest.main()
