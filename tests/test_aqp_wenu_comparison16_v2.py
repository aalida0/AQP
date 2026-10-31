#!/usr/bin/env python3
"""Static tests for isolated AQP Wenu existing-gridpack 16-core DAGs.

This does not invoke ATLAS, MadGraph, gridpack reads, or Condor.
"""
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
CONFIGS = ("standard111", "delta111", "delta221")
PIPELINE = ROOT / "condor/wenu_comparison16_v2"

class WenuComparison16V2Tests(unittest.TestCase):
    def test_all_shell_scripts_syntax(self):
        for s in ("stage_wenu_comparison_16core_v2.sh",
                  "run_wenu_comparison_16core_lhe.sh",
                  "run_wenu_comparison_16core_fxfx.sh"):
            with self.subTest(script=s):
                p = subprocess.run(["bash", "-n", str(ROOT / "scripts" / s)],
                                   capture_output=True, text=True, timeout=10)
                self.assertEqual(p.returncode, 0, p.stderr)

    def test_staging_is_read_only_and_branch_pinned(self):
        t = (ROOT / "scripts/stage_wenu_comparison_16core_v2.sh").read_text()
        self.assertIn('audit/production-framework', t)
        self.assertIn('audit_wenu_three_gridpack_candidates.py', t)
        self.assertIn('AQP_WENU_COMPARISON16_V2_STAGING_PASS', t)
        self.assertIn('STAGED_ONLY', t)
        self.assertNotIn('https://raw.githubusercontent.com/', t)
        self.assertNotIn('condor_submit_dag ', t.split('echo "STAGED_ONLY')[0])
        self.assertNotIn('condor_submit ', t.split('echo "STAGED_ONLY')[0])

    def test_all_joboptions_parse_and_use_expected_settings(self):
        for cfg in CONFIGS:
            with self.subTest(config=cfg):
                g = (ROOT / "joboptions/wenu_comparison16" / cfg /
                     "100003" / f"mc.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_{cfg}.py")
                s = (ROOT / "joboptions/wenu_comparison16_shower" / cfg /
                     "100004" / f"mc.aMCPy8EG_Wenu_FxFx_2jets_{cfg}_shower.py")
                for p in (g, s):
                    compile(p.read_text(), str(p), "exec")
                ge, sh = g.read_text(), s.read_text()
                self.assertIn("AQP_WENU_EXISTING_GRIDPACK_ONLY", ge)
                self.assertIn("AQP_WENU_PARALLEL_CONFIG_VERIFIED_MODE=2_NB_CORE", ge)
                self.assertIn("WENU_NB_CORES = 16", ge)
                self.assertIn("LHE_OVERSAMPLING_FACTOR = 5", ge)
                self.assertIn(f"AQP_WENU_SHOWER_CONFIG={cfg}", sh)
                self.assertIn("AQP_FXFX_SHOWER_MADGRAPH_NOT_INVOKED", sh)
                self.assertIn("PYTHIA8_nJetMax = 2", sh)
                self.assertIn("PYTHIA8_qCut = 20.0", sh)
                self.assertIn('SoftQCD:inelastic = off', sh)

    def test_dags_have_three_lhe_and_three_shower_nodes_no_retry(self):
        for name, tag, events in (("smoke.dag", "smoke16_1k", "1000"),
                                  ("pilot25k.dag", "pilot16_25k", "25000")):
            with self.subTest(name=name):
                t = (PIPELINE / name).read_text()
                self.assertEqual(len(re.findall(r"^JOB ", t, flags=re.M)), 6)
                self.assertEqual(len(re.findall(r"^PARENT ", t, flags=re.M)), 3)
                self.assertEqual(len(re.findall(r"^RETRY \S+ 0$", t, flags=re.M)), 6)
                self.assertEqual(t.count(f'NEVENTS="{events}"'), 6)
                self.assertEqual(t.count(f'TAG="{tag}"'), 6)
                for cfg in CONFIGS:
                    self.assertIn(f'CFG="{cfg}"', t)

    def test_submit_files_pin_audit_checkout(self):
        a = (PIPELINE / "lhe.submit").read_text()
        b = (PIPELINE / "shower.submit").read_text()
        for t in (a, b):
            self.assertIn("/home/aalida/AQP/aqp-production-audit/", t)
            self.assertNotIn("/home/aalida/AQP/Wjets/WENU/run_", t)
            self.assertIn("queue 1", t)
        self.assertIn("request_cpus = 16", a)
        self.assertIn("request_cpus = 1", b)
        self.assertIn("audit_wenu_delta441_lhe.py", a)

    def test_runner_uses_gridpack_and_checks_results(self):
        g = (ROOT / "scripts/run_wenu_comparison_16core_lhe.sh").read_text()
        s = (ROOT / "scripts/run_wenu_comparison_16core_fxfx.sh").read_text()
        for needle in ("_CONDOR_SCRATCH_DIR", "GRID.tar.gz", "sha256sum",
                       "AQP_WENU_EXISTING_GRIDPACK_ONLY",
                       "AQP_WENU_LHE_EVENTS_REQUESTED"):
            self.assertIn(needle, g)
        for needle in ("_CONDOR_SCRATCH_DIR", "AQP_FXFX_SHOWER_MADGRAPH_NOT_INVOKED",
                       "validated_LHE.events", "FxFx"):
            self.assertIn(needle, s)

if __name__ == "__main__":
    unittest.main()
