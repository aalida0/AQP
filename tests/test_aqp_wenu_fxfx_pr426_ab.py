#!/usr/bin/env python3
"""Static non-production audit of Wenu Standard111 FxFx PR426 A/B generation."""
from pathlib import Path
import ast
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
JOB=ROOT/"joboptions/wenu_fxfx_pr426_ab"
RUNNER=ROOT/"scripts/run_wenu_fxfx_pr426_ab.sh"
STAGER=ROOT/"scripts/stage_wenu_fxfx_pr426_ab.sh"

def jo(case):
    return (JOB/case/"100005"/
            ("mc.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_%s.py" % case))

class Tests(unittest.TestCase):
    def test_both_joboptions_compile(self):
        for case in ("before", "after"):
            path=jo(case)
            compile(path.read_text(),str(path),"exec")
            self.assertIn("grid_pack=False",path.read_text())

    def test_same_code_except_case_and_patch_flag(self):
        before=jo("before").read_text()
        after=jo("after").read_text()
        self.assertEqual(
            before.replace('FXFX_APPLY_PR426 = False','FXFX_APPLY_PR426 = True')
                  .replace('FXFX_CASE = "before"', 'FXFX_CASE = "after"'),
            after
        )

    def test_original_ht2_and_13tev_folding(self):
        t=jo("before").read_text()
        for needle in ("montecarlocounter_MINE.f", "dummy_fct.f",
                       "event_norm\": \"bias\"", "REQUIRED_ACCURACY = 0.1",
                       'FOLDING = "1, 1, 1"', "WENU_NB_CORES = 16",
                       '\"mcatnlo_delta\": USE_DELTA',
                       "if is_gen_from_gridpack()",
                       "AQP_FXFX_AB_REQUIRE_COMPUTE_WORKER",
                       "aqp_prepare_fxfx_exclusive_kt_patch.py"):
            if needle=="AQP_FXFX_AB_REQUIRE_COMPUTE_WORKER":
                self.assertIn("AQP_FXFX_AB_REQUIRE_COMPUTE_WORKER",t)
            else:
                self.assertIn(needle,t)

    def test_corrected_process_source_only_after_new_process(self):
        t=jo("after").read_text()
        self.assertLess(t.index("new_process(process)"),t.index("cuts_path.write_text"))
        self.assertLess(t.index("cuts_path.write_text"),t.index("generate("))
        self.assertIn("mod.patched_text(before)", t)
        self.assertNotIn("enable_condor_timing",t)
        self.assertNotIn("grid_pack=True",t)

    def test_shell_syntax(self):
        for p in (RUNNER,STAGER):
            with self.subTest(path=p):
                result=subprocess.run(["bash","-n",str(p)],
                    capture_output=True,text=True,timeout=10)
                self.assertEqual(result.returncode,0,result.stderr)

    def test_submit_configs_two_variants_and_no_internal_condor(self):
        for name, count in (("smoke200",200),("benchmark50k",50000)):
            text=(ROOT/"condor"/f"wenu_fxfx_pr426_{name}.submit").read_text()
            self.assertIn("request_cpus = 16",text)
            self.assertIn("queue CASE from (",text)
            self.assertIn("\nbefore\nafter\n",text)
            self.assertIn(f"arguments = $(CASE) {count}",text)
            self.assertIn("aqp_prepare_fxfx_exclusive_kt_patch.py",text)
            self.assertIn("montecarlocounter_MINE.f",text)
            self.assertIn("dummy_fct.f",text)

    def test_runner_hard_guards_and_benchmark_gate(self):
        text=RUNNER.read_text()
        for need in ("_CONDOR_SCRATCH_DIR", "50000", "200",
                     "smoke200_", "if [[ \"$NEVENTS\" == 50000 ]]",
                     "Gen_tf.py", "AQP_FXFX_AB_LHE_VALIDATED"):
            self.assertIn(need,text)
        self.assertNotIn("condor_submit ",text)
        self.assertNotIn("gridpacks/",text)

if __name__=="__main__":
    unittest.main()
