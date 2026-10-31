#!/usr/bin/env python3
"""Offline checks for Wenu FxFx PR426 saved-grid re-use, no Condor/MadGraph jobs."""
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
JOS=ROOT/"joboptions/wenu_fxfx_pr426_internal_condor"
REUSE=ROOT/"scripts/run_wenu_fxfx_pr426_reuse_50k.sh"
AUDIT=ROOT/"scripts/check_wenu_fxfx_pr426_saved_grids.py"

def jo(which):
    return JOS/which/"100006"/f"mc.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_{which}.py"

class SavedGridReuse(unittest.TestCase):
    def test_both_joboptions_preserve_generated_process_and_disable_variations(self):
        for version in ("before","after"):
            with self.subTest(version=version):
                s=jo(version).read_text()
                compile(s,str(jo(version)),"exec")
                for token in ('saveProcDir=True',
                              'MADGRAPH_PDFSETTING = None',
                              '"lhaid": 325100',
                              '"systematics_program": "none"',
                              'grid_pack=False',
                              'REQUIRED_ACCURACY = 0.1',
                              '"run_mode": 1'):
                    self.assertIn(token,s)
                self.assertNotIn('saveProcDir=False',s)
                self.assertNotIn('"pdf_variations": []',s)
                self.assertNotIn('"scale_variations": []',s)

    def test_before_after_physics_only_patch_difference(self):
        b=jo("before").read_text()
        a=jo("after").read_text()
        self.assertEqual(b.replace(
            "FXFX_APPLY_PR426 = False", "FXFX_APPLY_PR426 = True").replace(
            'FXFX_CASE = "before"', 'FXFX_CASE = "after"'), a)

    def test_saved_grids_audit_syntax_and_decompressed_lhe_support(self):
        p=subprocess.run(["python3","-m","py_compile",str(AUDIT)],
                         capture_output=True,text=True,timeout=5)
        self.assertEqual(p.returncode,0,p.stderr)
        txt=AUDIT.read_text()
        self.assertIn('Events/run_01/events.lhe"',txt)
        self.assertIn('Events/run_01/events.lhe.gz"',txt)
        self.assertIn('GF*/mint_grids',txt)
        self.assertIn('job_status.pkl',txt)
        self.assertIn('starts != 200',txt)

    def test_generation_shell_syntax_and_only_generation_flags(self):
        p=subprocess.run(["bash","-n",str(REUSE)],
                         capture_output=True,text=True,timeout=5)
        self.assertEqual(p.returncode,0,p.stderr)
        txt=REUSE.read_text()
        for token in ("launch -f -c -p -o -x --name",
                      "nevents", "50000", "iseed", "411",
                      "--check", "--execute",
                      "aMCatNLO_exit_code","AQP_FXFX_PR426_50000_LHE_PASS"):
            self.assertIn(token,txt)
        self.assertNotIn('grid_pack=True',txt)

if __name__=="__main__":
    unittest.main()
