#!/usr/bin/env python3
"""Synthetic, read-only tests of the generated MadGraph GF worker audit."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "aqp_audit_generated_ajob1_worker.py"
spec = importlib.util.spec_from_file_location("aqp_audit_generated_ajob1_worker", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

WORKER = """#!/bin/bash
script=ajob1.$1.$2.$3.$4
channel=$1
run_mode=$2
runnumber=$3
integration_step=$4
for i in 1 ; do
    j=G$run_mode$i
    cd "$j"
    ../madevent_mintMC > log.txt <input_app.txt 2>&1
    status=$?
    cp -f log.txt log_MINT$integration_step.txt >/dev/null 2>&1
    cp -f res.dat res_$integration_step.dat >/dev/null 2>&1
    exit $status
done
"""

class WorkerAuditTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.channel = (self.base / "standard111" /
                        "PROCNLO_loop_sm-no_b_mass_0" / "SubProcesses" /
                        "P2_testr")
        self.channel.mkdir(parents=True)
        (self.channel / "ajob1").write_text(WORKER)
        (self.channel / "G0_1").mkdir()

    def test_stage_arguments_detected(self):
        flags = mod.analyze_text(WORKER)
        self.assertTrue(all(flags.values()), flags)

    def test_copy_success_not_inferred_from_worker_exit(self):
        result = mod.analyze_channel(self.channel)
        self.assertTrue(result["has_ajob1"])
        self.assertFalse(result["copy_result_checked_by_exit_code"])
        self.assertFalse(result["request_id_present"])

    def test_stage_outputs_are_observed_not_certified(self):
        folder = self.channel / "G0_1"
        (folder / "res_1.dat").write_bytes(b"fake stage 1")
        (folder / "log_MINT1.txt").write_bytes(b"fake stage log")
        result = mod.analyze_channel(self.channel)
        self.assertEqual(result["observed_stage_file_counts"]["res_1.dat"], 1)
        self.assertEqual(result["observed_stage_file_counts"]["log_MINT1.txt"], 1)
        self.assertEqual(result["observed_stage_file_counts"]["res_0.dat"], 0)

    def test_missing_worker_is_reported_not_guessed(self):
        (self.channel / "ajob1").unlink()
        result = mod.analyze_channel(self.channel)
        self.assertFalse(result["has_ajob1"])

    def test_symlinked_worker_is_rejected(self):
        source = self.channel / "ajob_source"
        source.write_text(WORKER)
        (self.channel / "ajob1").unlink()
        (self.channel / "ajob1").symlink_to(source)
        result = mod.analyze_channel(self.channel)
        self.assertFalse(result["has_ajob1"])

    def test_symlinked_result_is_not_counted(self):
        folder = self.channel / "G0_1"
        (folder / "other.dat").write_bytes(b"test")
        (folder / "res_1.dat").symlink_to(folder / "other.dat")
        result = mod.analyze_channel(self.channel)
        self.assertEqual(result["observed_stage_file_counts"]["res_1.dat"], 0)

    def test_summary_refuses_to_claim_worker_contract_verified(self):
        summary = mod.audit_config(self.base, "standard111")
        self.assertFalse(summary["contract_verified"])
        self.assertEqual(summary["channel_dirs"], 1)
        self.assertEqual(summary["channels_with_ajob1"], 1)
        self.assertEqual(summary["unchecked_result_copy_count"], 1)

    def test_audit_leaves_source_files_unchanged(self):
        source = self.channel / "ajob1"
        before = source.read_bytes()
        mod.audit_config(self.base, "standard111")
        self.assertEqual(source.read_bytes(), before)

if __name__ == "__main__":
    unittest.main()
