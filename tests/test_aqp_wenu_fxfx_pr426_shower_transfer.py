#!/usr/bin/env python3
"""Static regression: independent PR426 FxFx worker with native file transfer.

No AF/Condor access needed. These tests do not submit or generate events.
"""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SUBMIT = ROOT / "condor/wenu_fxfx_pr426_before_18000_shower.submit"
WORKER = ROOT / "scripts/run_wenu_fxfx_pr426_condor_transfer.sh"
STAGE = ROOT / "scripts/stage_wenu_fxfx_pr426_before_18000_transfer.sh"


class TransferTest(unittest.TestCase):
    def test_batch_no_shared_filesystem_constraint(self):
        text = SUBMIT.read_text()
        for expected in (
            "should_transfer_files = YES",
            "transfer_executable = True",
            "when_to_transfer_output = ON_EXIT",
            "transfer_input_files = ",
            "transfer_output_files = shower_artifacts,wenu_pr426_before_accepted18000.EVNT.pool.root",
            "transfer_output_remaps = ",
            "wenu_pr426_before_accepted18000.EVNT.pool.root = /data/aalida/AQP/",
            "source_50k_lhe.gz",
            "source_50k_lhe.sha256",
            "joboptions/wenu_fxfx_pr426_shower/100007",
            "request_cpus = 1",
            "request_memory = 8000MB",
            "request_disk = 8000MB",
            "initialdir = /home/aalida/AQP/",
        ):
            self.assertIn(expected, text)
        for forbidden in (
            "should_transfer_files = NO",
            "FileSystemDomain = ",
            "TARGET.FileSystemDomain",
            "getenv = True",
            "condor_submit -interactive",
            "initialdir = /data/",
        ):
            self.assertNotIn(forbidden, text)

    def test_worker_shell_parses_and_is_scratch_local(self):
        text = WORKER.read_text()
        p = subprocess.run(["bash", "-n", str(WORKER)],
                           capture_output=True, text=True, timeout=5)
        self.assertEqual(p.returncode, 0, p.stderr)
        for expected in (
            "_CONDOR_SCRATCH_DIR",
            "evnt_transfer_status.txt",
            "source_50k_lhe.gz",
            "source_50k_lhe.sha256",
            "100007/mc.aMCPy8EG_Wenu_FxFx_2jets_PR426_shower.py",
            "shower_artifacts",
            "runner_exit_code",
            "Gen_tf.py",
            "--inputGeneratorFile=input.events",
            "AQP_FXFX_PR426_CASE",
            "JetMatchingMadgraph",
            "gzip -cd",
        ):
            self.assertIn(expected, text)
        for forbidden in ("/home/aalida", "/data/aalida", "condor_submit", "grid_pack"):
            self.assertNotIn(forbidden, text)

    def test_stage_shell_parses_and_is_fail_closed(self):
        text = STAGE.read_text()
        p = subprocess.run(["bash", "-n", str(STAGE)],
                           capture_output=True, text=True, timeout=5)
        self.assertEqual(p.returncode, 0, p.stderr)
        for expected in ("4059847.0", "condor_rm",
                         "sha256sum", "gzip -t", "mkdir",
                         "stage_manifest.txt", "bash -n",
                         "SUBMIT_INITIALDIR", "REUSING_REJECTED_SUBMISSION_STAGE",
                         "EVNT or returned diagnostics already exist"):
            self.assertIn(expected, text)


if __name__ == "__main__":
    unittest.main()
