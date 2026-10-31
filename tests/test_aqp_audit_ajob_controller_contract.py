#!/usr/bin/env python3
"""Synthetic source-audit tests for actual MG job/required_output contracts."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

FILE = Path(__file__).resolve().parents[1] / "scripts" / "aqp_audit_ajob_controller_contract.py"
spec = importlib.util.spec_from_file_location("aqp_audit_ajob_controller_contract", FILE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

INTERFACE = """class aMCatNLOCmd:
    def run_all_jobs(self, jobs_to_run, integration_step):
        for job in jobs_to_run:
            arguments=[job['channel'],job['run_mode'],str(job['split']),str(integration_step)]
            self.run_exe('ajob1', arguments, 'mode', cwd='test')

    def getIO_ajob(self, exe, cwd, args):
        input_files, output_files, required_output = [], [], []
        if args[1] == 'F' or args[1] == 'B':
            required_output.append('G%s%s/log_MINT%s.txt')
            if args[3] in ['0','1']:
                required_output.append('results.dat')
        return input_files, output_files, required_output, args
"""
CLUSTER = """def store_input(arg=''):
    def deco_store(f):
        def deco_f_store(self, prog, argument=[], cwd=None):
            id = f(self, prog, argument, cwd)
            if self.nb_retry > 0:
                self.retry_args[id] = args
            return id
        return deco_f_store
    return deco_store

class Cluster:
    def check_termination(self, job_id):
        args = self.retry_args[job_id]
        for path in args['required_output']:
            pass
"""

class ContractTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.interface = self.root / 'amcatnlo_run_interface.py'
        self.cluster = self.root / 'cluster.py'
        self.interface.write_text(INTERFACE)
        self.cluster.write_text(CLUSTER)

    def test_extracts_nested_interface_methods(self):
        result = audit.audit(self.interface, self.cluster)
        self.assertEqual(result["controller"]["getIO_ajob_first_line"], 7)

    def test_run_mode_stage_identity_fields_exist(self):
        result = audit.audit(self.interface, self.cluster)
        self.assertTrue(result["observed_flags"]["worker_arguments_include_four_fields"])

    def test_output_contract_has_required_output_paths(self):
        result = audit.audit(self.interface, self.cluster)
        self.assertTrue(result["observed_flags"]["mintmc_F_B_branches_present"])
        self.assertTrue(result["observed_flags"]["mintmc_log_MINT_required"])
        self.assertTrue(result["observed_flags"]["worker_outputs_derived_from_getIO"])

    def test_retry_state_only_created_conditionally(self):
        result = audit.audit(self.interface, self.cluster)
        self.assertTrue(result["observed_flags"]["retry_args_conditional_on_nb_retry"])

    def test_source_audit_not_approval(self):
        result = audit.audit(self.interface, self.cluster)
        self.assertFalse(result["approved_for_worker_patch"])
        self.assertTrue(result["source_evidence_only"])

    def test_class_name_drift_is_rejected(self):
        self.interface.write_text(INTERFACE.replace("aMCatNLOCmd", "Other"))
        with self.assertRaisesRegex(ValueError, "Missing unique source class"):
            audit.audit(self.interface, self.cluster)

    def test_does_not_modify_original_source(self):
        initial_interface = self.interface.read_bytes()
        initial_cluster = self.cluster.read_bytes()
        audit.audit(self.interface, self.cluster)
        self.assertEqual(self.interface.read_bytes(), initial_interface)
        self.assertEqual(self.cluster.read_bytes(), initial_cluster)

if __name__ == "__main__":
    unittest.main()
