"""Static guards for PR426 2-jet FxFx production-gridpack smoke workflow."""
import ast
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]
DIR = REPO / "tests" / "2jet" / "999998"
JO = DIR / "mc.aMCPy8EG_Zee_FxFx_2jets_DRjj_PR426.py"
PATCH = DIR / "fxfx_exclusive_kt.patch"
SMOKE = REPO / "scripts" / "validate_zee2jet_pr426_gridpack.sh"
OLD_PATCH = REPO / "tests" / "1jet" / "999999" / "fxfx_exclusive_kt.patch"


class PR426Zee2JetTests(unittest.TestCase):
    def test_local_patch_is_exact_existing_upstream_pr426(self):
        self.assertEqual(PATCH.read_bytes(), OLD_PATCH.read_bytes())
        patch = PATCH.read_text()
        self.assertIn("+         call amcatnlo_fastjetppgenkt_timed(", patch)
        self.assertIn("+         if (amcatnlo_fastjetdmergemax(nQCD-2).lt.ptj**2) then", patch)
        self.assertIn("-      call amcatnlo_fastjetppgenkt_etamax_timed(", patch)
        self.assertIn("--- a/SubProcesses/cuts.f", patch)
        self.assertIn("+++ b/SubProcesses/cuts.f", patch)

    def test_integrated_at_nlo_up_to_two_jets(self):
        text = JO.read_text()
        tree = ast.parse(text, filename=str(JO))
        self.assertNotIn("AQP", text)
        self.assertIn("generate p p > e+ e- [QCD] @0", text)
        self.assertIn("add process p p > e+ e- j [QCD] @1", text)
        self.assertIn("add process p p > e+ e- j j [QCD] @2", text)
        assignments = {node.targets[0].id: node.value.value
                       for node in ast.walk(tree)
                       if isinstance(node, ast.Assign)
                       and len(node.targets) == 1
                       and isinstance(node.targets[0], ast.Name)
                       and isinstance(node.value, ast.Constant)}
        self.assertEqual(assignments["REQUIRED_ACCURACY"], 1e-4)
        self.assertEqual(assignments["FOLDING"], "1, 1, 1")
        self.assertFalse(assignments["USE_DELTA"])
        self.assertIn('    PYTHIA8_nJetMax = 2', text)
        self.assertIn('    PYTHIA8_qCut = 20.0', text)
        self.assertIn('"ickkw": 3', text)

    def test_pr426_applied_before_integration(self):
        text = JO.read_text()
        self.assertLess(
            text.index('    subprocess.check_call(command)'),
            text.index('generate(process_dir=process_dir, runArgs=runArgs,'))
        self.assertIn('command + ["--dry-run"]', text)
        self.assertIn('FXFX_PR426_EXCLUSIVE_KT_VERIFIED', text)
        self.assertIn('process_dir = str(MADGRAPH_GRIDPACK_LOCATION)', text)
        self.assertIn('grid_pack=GRIDPACK_MODE', text)

    def test_pmg_variations_not_dropped(self):
        text = JO.read_text()
        self.assertIn('MG.MADGRAPH_PDFSETTING = {', text)
        self.assertIn('"central_pdf": 325100', text)
        self.assertIn('"pdf_variations": [325100, 93300]', text)
        self.assertIn('MGC.MADGRAPH_PDFSETTING = MG.MADGRAPH_PDFSETTING', text)
        self.assertIn('"store_rwgt_info": not GRIDPACK_MODE', text)

    def test_2jet_smoke_uses_own_jo_and_recompile(self):
        script = SMOKE.read_text()
        self.assertIn('jo="$repo/tests/2jet/999998"', script)
        self.assertIn('export GRIDPACK_RECOMPILE=1', script)
        self.assertIn('zee2jet.EVNT.pool.root', script)
        self.assertIn('evnt_count_verified.txt', script)


if __name__ == "__main__":
    unittest.main()
