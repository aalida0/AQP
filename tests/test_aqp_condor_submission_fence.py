#!/usr/bin/env python3
"""Regression tests for the UNDEPLOYED bundled MG5 Condor submission fence.

Pure Python. The test imports generated candidate methods into a synthetic
environment with an in-memory condor_submit subprocess, never HTCondor.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from aqp_prepare_condor_submission_fence import patch_text

SOURCE = '''import sys
class CondorCluster:
    def submit(self, prog, argument=[], cwd=None):
        text = """Executable = %(prog)s
                  %(requirement)s
                  queue 1
               """
        if cwd is None:
            cwd = os.getcwd()
        if argument:
            argument = 'Arguments = %s' % ' '.join(argument)
        else:
            argument = ''
        dico = {'prog': prog, 'requirement': ''}
        a = misc.Popen(['condor_submit'], stdout=subprocess.PIPE,
                       stdin=subprocess.PIPE)
        output, _ = a.communicate((text % dico).encode())
        if a.returncode != 0:
            raise ClusterManagmentError('condor_submit failure')
        if b'submitted to cluster' not in output:
            raise ClusterManagmentError('ambiguous submit acknowledgment')
        id = '910001'
        self.submitted += 1
        self.submitted_ids.append(id)
        return id

    def submit2(self, prog, argument=[], cwd=None, input_files=[]):
        if not input_files:
            return self.submit(prog, argument, cwd)
        text = """Executable = %(prog)s
                  %(requirement)s
                  queue 1
               """
        if cwd is None:
            cwd = os.getcwd()
        if argument:
            argument = 'Arguments = %s' % ' '.join(argument)
        else:
            argument = ''
        dico = {'prog': prog, 'requirement': ''}
        a = subprocess.Popen(['condor_submit'], stdout=subprocess.PIPE,
                             stdin=subprocess.PIPE)
        output, _ = a.communicate((text % dico).encode())
        if a.returncode != 0:
            raise ClusterManagmentError('condor_submit failure')
        if b'submitted to cluster' not in output:
            raise ClusterManagmentError('ambiguous submit acknowledgment')
        id = '910002'
        self.submitted += 1
        self.submitted_ids.append(id)
        return id
'''


class FakeChild:
    returncode = 0

    def __init__(self, recorded, has_ack):
        self.recorded, self.has_ack = recorded, has_ack

    def communicate(self, payload):
        self.recorded.append(payload.decode())
        if self.has_ack:
            return b'1 job(s) submitted to cluster 910001.\n', b''
        return b'Submitting job(s).\n', b''


class SubmissionFenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        package = self.root / "internal"
        package.mkdir()
        (package / "__init__.py").touch()
        for name in ("aqp_condor_submission_guard.py", "aqp_condor_intent_ledger.py"):
            (package / name).write_bytes((SCRIPTS / name).read_bytes())
        self.cwd = self.root / "P2_test"
        self.cwd.mkdir()
        self.prog = self.root / "ajob1"
        self.prog.touch()
        sys.path.insert(0, str(self.root))
        self.addCleanup(lambda: sys.path.remove(str(self.root)))
        self.addCleanup(self._unload_internal)
        self.submissions = []
        self.has_ack = True

        def fake_popen(*args, **kwargs):
            return FakeChild(self.submissions, self.has_ack)

        env = {
            "os": os,
            "subprocess": SimpleNamespace(PIPE=subprocess.PIPE, Popen=fake_popen),
            "misc": SimpleNamespace(Popen=fake_popen),
            "ClusterManagmentError": RuntimeError,
        }
        exec(patch_text(SOURCE), env)
        self.controller = env["CondorCluster"]()
        self.controller.submitted = 0
        self.controller.submitted_ids = []
        self.environment = patch.dict(os.environ,
                                      {"AQP_CONDOR_INTENT_ROOT": str(self.root)})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def _unload_internal(self):
        for key in list(sys.modules):
            if key == "internal" or key.startswith("internal."):
                del sys.modules[key]

    @staticmethod
    def args(gf="GF7.0", stage="1"):
        return [gf, "second", "third", stage]

    def count_intents(self):
        return len([f for f in self.root.glob("*.json") if len(f.stem) == 64])

    def test_both_methods_patched(self):
        result = patch_text(SOURCE)
        self.assertEqual(result.count("_aqp_submission_guard.reserve("), 2)
        self.assertEqual(result.count("_aqp_submission_guard.acknowledge("), 2)
        self.assertEqual(result.count("+AQPRequestId ="), 2)

    def test_success_has_classad_and_durable_ack(self):
        self.controller.submit(str(self.prog), self.args(), str(self.cwd))
        self.assertEqual(len(self.submissions), 1)
        self.assertIn('+AQPRequestId = "AQP', self.submissions[0])
        self.assertEqual(self.count_intents(), 1)
        self.assertEqual(len(list(self.root.glob("ack_*.json"))), 1)

    def test_duplicate_attempt_rejected_before_submission(self):
        self.controller.submit(str(self.prog), self.args(), str(self.cwd))
        with self.assertRaisesRegex(Exception, "Existing GF submission intent"):
            self.controller.submit(str(self.prog), self.args(), str(self.cwd))
        self.assertEqual(len(self.submissions), 1)

    def test_lost_ack_leaves_unresolved_intent(self):
        self.has_ack = False
        with self.assertRaisesRegex(RuntimeError, "ambiguous submit acknowledgment"):
            self.controller.submit(str(self.prog), self.args(), str(self.cwd))
        self.has_ack = True
        with self.assertRaisesRegex(Exception, "Existing GF submission intent"):
            self.controller.submit(str(self.prog), self.args(), str(self.cwd))
        self.assertEqual(len(self.submissions), 1)
        self.assertEqual(self.count_intents(), 1)
        self.assertFalse(list(self.root.glob("ack_*.json")))

    def test_submit2_delegation_does_not_claim_twice(self):
        self.controller.submit2(str(self.prog), self.args(), str(self.cwd))
        self.assertEqual(len(self.submissions), 1)
        self.assertEqual(self.count_intents(), 1)

    def test_submit2_dedicated_path(self):
        self.controller.submit2(str(self.prog), self.args(), str(self.cwd),
                                input_files=["example.dat"])
        self.assertEqual(len(self.submissions), 1)
        self.assertEqual(self.count_intents(), 1)
        self.assertIn("+AQPRequestId =", self.submissions[0])

    def test_two_stages_get_distinct_intents(self):
        self.controller.submit(str(self.prog), self.args(stage="0"), str(self.cwd))
        self.controller.submit(str(self.prog), self.args(stage="1"), str(self.cwd))
        self.assertEqual(self.count_intents(), 2)

    def test_missing_ledger_configuration_fails_before_submit(self):
        del os.environ["AQP_CONDOR_INTENT_ROOT"]
        with self.assertRaisesRegex(Exception, "AQP_CONDOR_INTENT_ROOT"):
            self.controller.submit(str(self.prog), self.args(), str(self.cwd))
        self.assertFalse(self.submissions)

    def test_unknown_job_type_fails_before_submit(self):
        with self.assertRaisesRegex(Exception, "Unrecognized executable"):
            self.controller.submit("/bin/true", self.args(), str(self.cwd))
        self.assertFalse(self.submissions)

    def test_unknown_stage_fails_before_submit(self):
        with self.assertRaisesRegex(Exception, "Unknown GF/stage"):
            self.controller.submit(str(self.prog), self.args(stage="7"), str(self.cwd))
        self.assertFalse(self.submissions)

    def test_unknown_source_layout_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "submit text"):
            patch_text(SOURCE.replace('text = """Executable',
                                      'text = """Unknown', 1))


if __name__ == "__main__":
    unittest.main()
