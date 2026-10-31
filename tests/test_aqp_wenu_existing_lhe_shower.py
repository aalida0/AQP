#!/usr/bin/env python3
"""Offline syntax/provenance gates for the 1000-LHE Wenu FxFx-only pilot."""
from pathlib import Path
import subprocess
import unittest

REPO = Path(__file__).resolve().parents[1]
CONFIGS = ("standard111", "delta111", "delta221")


class ExistingLHEShowerTests(unittest.TestCase):
    def test_scripts_parse(self):
        for name in ("run_wenu_existing_lhe_shower.sh",
                     "stage_wenu_existing_lhe_shower.sh"):
            with self.subTest(name=name):
                result = subprocess.run(
                    ["bash", "-n", str(REPO / "scripts" / name)],
                    capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_full_joboptions_compilable_no_madgraph(self):
        for config in CONFIGS:
            with self.subTest(config=config):
                path = (
                    REPO / "joboptions" / "wenu_existing_lhe_shower" /
                    config / "100004" /
                    ("mc.aMCPy8EG_Wenu_FxFx_2jets_%s_shower.py" % config)
                )
                text = path.read_text()
                compile(text, str(path), "exec")
                self.assertIn("AQP_WENU_SHOWER_CONFIG=%s" % config, text)
                self.assertIn("AQP_FXFX_SHOWER_MADGRAPH_NOT_INVOKED", text)
                self.assertIn('include("Pythia8_i/Pythia8_FxFx_A14mod.py")', text)
                self.assertIn("SoftQCD:inelastic = off", text)
                self.assertNotIn("MadGraphControl", text)
                self.assertNotIn("generate(", text)
                self.assertNotIn("new_process(", text)

    def test_runner_requires_original_input_and_pinned_sha(self):
        script = (REPO / "scripts/run_wenu_existing_lhe_shower.sh").read_text()
        self.assertIn("EXPECTED_SHA", script)
        self.assertIn("sha256sum", script)
        self.assertIn("gzip -t", script)
        self.assertIn("--expected-events 1000", script)
        self.assertIn("--inputGeneratorFile=recovered.events", script)
        self.assertIn("--maxEvents=200", script)
        self.assertIn("mkdir \"$OUT\"", script)
        self.assertNotIn("new_process(", script)
        self.assertNotIn("MINT1", script)
        self.assertNotIn("Gen_tf.py --outputTXTFile", script)

    def test_condor_manifest_and_no_auto_retry(self):
        submission = (REPO / "condor/wenu_existing_lhe_shower.submit").read_text()
        self.assertIn("queue CFG,SHA from", submission)
        self.assertIn("request_cpus = 1", submission)
        self.assertIn("transfer_input_files", submission)
        self.assertNotIn("periodic_release", submission)
        self.assertNotIn("max_retries", submission)
        self.assertNotIn("queue 3", submission)


if __name__ == "__main__":
    unittest.main()
