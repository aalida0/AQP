#!/usr/bin/env python3
"""Static audit: Wenu Standard111 PR426 A/B runs using MG internal Condor."""
from pathlib import Path
import ast
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
DIRECT=ROOT/"joboptions/wenu_fxfx_pr426_internal_condor"

def jo(variant):
    return (DIRECT/variant/"100006"/
      f"mc.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_{variant}.py")

class InternalCondorAbTests(unittest.TestCase):
    def test_both_complete_joboptions_parse(self):
        for version in ("before","after"):
            p=jo(version)
            compile(p.read_text(),str(p),"exec")

    def test_identical_except_pr426_flag_and_label(self):
        b=jo("before").read_text()
        a=jo("after").read_text()
        self.assertEqual(
            b.replace("FXFX_APPLY_PR426 = False", "FXFX_APPLY_PR426 = True")
             .replace('FXFX_CASE = "before"', 'FXFX_CASE = "after"'),a)

    def test_internal_condor_settings_and_fresh_process(self):
        s=jo("before").read_text()
        for needle in ('"run_mode": 1','"nb_core": compile_cores',
                       '"cluster_type": "condor"','"cluster_size": 100',
                       "new_process(process)","grid_pack=False",
                       "REQUIRED_ACCURACY = 0.1", "FOLDING = \"1, 1, 1\"",
                       "USE_DELTA = False", "dummy_fct.f",
                       "montecarlocounter_MINE.f",
                       "AQP_FXFX_AB_INTERNAL_CONDOR_MODE=1_CLUSTER_SIZE=100",
                       "AQP_FXFX_AB_COMPILE_CORES=%d", 
                       "AQP_FXFX_AB_COMPILE_CORES_MUST_BE_4_16_24_OR_32"):
            self.assertIn(needle,s)
        self.assertNotIn('enable_condor_timing',s)
        self.assertNotIn('AQP_FXFX_AB_LOCAL_MULTICORE_MODE',s)

    def test_process_patch_applied_after_new_process_before_generate(self):
        s=jo("after").read_text()
        self.assertLess(s.index("new_process(process)"),s.index("cuts_path.write_text"))
        self.assertLess(s.index("cuts_path.write_text"),s.index("generate("))
        self.assertIn("mod.patched_text(before)",s)

    def test_runner_syntax_and_reuse_guards(self):
        p=ROOT/"scripts/run_wenu_fxfx_pr426_internal_condor.sh"
        run=subprocess.run(["bash","-n",str(p)],capture_output=True,text=True,timeout=10)
        self.assertEqual(run.returncode,0,run.stderr)
        txt=p.read_text()
        for needle in ("Gen_tf.py", "runner_exit_code", "work directory already exists",
                       "condor_q", "200|50000", "AQP_FXFX_AB_LHE_VALIDATED"):
            self.assertIn(needle,txt)
        self.assertNotIn("gridpacks/",txt)
        self.assertNotIn("condor_rm",txt)
        self.assertIn('login*|head*',txt)
        self.assertIn('4|16|24|32',txt)
        self.assertIn('COMPILE_CORES > 4',txt)
        self.assertIn('AVAILABLE_CPUS="$(nproc)"',txt)
        self.assertIn('AQP_FXFX_AB_COMPILE_CORES=$COMPILE_CORES',txt)

if __name__=="__main__":
    unittest.main()
