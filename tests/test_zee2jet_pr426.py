"""Static regression gates for PR426 FxFx Zee 0,1,2j standard111 and delta111."""
import ast
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]
STDSID = REPO / "tests" / "2jet" / "999998"
DELTASID = REPO / "tests" / "2jet" / "999997"
JOS = {
    "standard111": STDSID / "mc.aMCPy8EG_Zee_FxFx_2jets_DRjj_PR426.py",
    "delta111": DELTASID / "mc.aMCPy8EG_Zee_FxFx_2jets_DRjj_PR426_delta111.py",
}
PATCHES = {cfg: directory / "fxfx_exclusive_kt.patch"
           for cfg, directory in (("standard111", STDSID),
                                  ("delta111", DELTASID))}
ORIGINAL_PATCH = (
    REPO / "tests" / "1jet" / "999999" / "fxfx_exclusive_kt.patch"
)
RUNNERS = {
    "standard111": REPO / "scripts" / "validate_zee2jet_pr426_gridpack.sh",
    "delta111": REPO / "scripts" / "validate_zee2jet_pr426_delta111_gridpack.sh",
}


def assignment_values(source):
    tree = ast.parse(source)
    assignments = {}
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Constant)):
            assignments[node.targets[0].id] = node.value.value
    return assignments


class PR426Zee2JetTests(unittest.TestCase):
    def test_patches_identical_to_previously_verified_upstream_pr426(self):
        original = ORIGINAL_PATCH.read_bytes()
        for config, patch in PATCHES.items():
            with self.subTest(config=config):
                self.assertEqual(patch.read_bytes(), original)
        text = original.decode()
        self.assertIn("+         call amcatnlo_fastjetppgenkt_timed(", text)
        self.assertIn("+         if (amcatnlo_fastjetdmergemax(nQCD-2).lt.ptj**2) then", text)
        self.assertIn("-      call amcatnlo_fastjetppgenkt_etamax_timed(", text)

    def test_both_integrate_same_nlo_0_1_2_jet_process(self):
        for config, jo in JOS.items():
            with self.subTest(config=config):
                text = jo.read_text()
                assignments = assignment_values(text)
                self.assertNotIn("AQP", text)
                self.assertIn("generate p p > e+ e- [QCD] @0", text)
                self.assertIn("add process p p > e+ e- j [QCD] @1", text)
                self.assertIn("add process p p > e+ e- j j [QCD] @2", text)
                self.assertEqual(assignments["REQUIRED_ACCURACY"], 0.5)
                self.assertEqual(assignments["FOLDING"], "1, 1, 1")
                self.assertEqual(assignments["USE_DELTA"], config == "delta111")
                self.assertIn('PYTHIA8_nJetMax = 2', text)
                self.assertIn('PYTHIA8_qCut = 20.0', text)
                self.assertIn('"ickkw": 3', text)
                self.assertIn('"mcatnlo_delta": USE_DELTA', text)
                self.assertIn('"folding": FOLDING', text)
                self.assertIn('"req_acc": REQUIRED_ACCURACY', text)
                self.assertIn('required_accuracy=REQUIRED_ACCURACY', text)

    def test_only_intentional_standard_vs_delta_differences(self):
        standard = JOS["standard111"].read_text()
        delta = JOS["delta111"].read_text()
        # Only the matching mode, description and required Pythia8
        # compile dependency may differ. The Sudakov calculation in
        # MC@NLO-Delta needs Pythia8 even during noshower integration.
        start = "# MC@NLO-Delta needs Pythia8 compiled into the MadGraph"
        end = "modify_config_card(process_dir=process_dir, settings=config_settings)"
        self.assertIn(start, delta)
        delta_without_pythia_setup = delta[:delta.index(start)] + delta[
            delta.index(end, delta.index(start)):
        ]
        normalized_delta = delta_without_pythia_setup.replace(
            "USE_DELTA = True", "USE_DELTA = False"
        ).replace("PR426 delta111 accuracy0p5 smoke",
                  "PR426 standard111 accuracy0p5 smoke")
        self.assertEqual(standard, normalized_delta)

    def test_delta_requires_real_pythia8_static_library(self):
        standard = JOS["standard111"].read_text()
        delta = JOS["delta111"].read_text()
        self.assertIn('pythia8_path = os.environ.get("PY8PATH")', delta)
        self.assertIn('os.path.join(pythia8_path, "lib", "libpythia8.a")', delta)
        self.assertIn('config_settings["pythia8_path"] = pythia8_path', delta)
        self.assertIn('MCATNLO_DELTA_PYTHIA8_PATH', delta)
        self.assertNotIn('config_settings["pythia8_path"]', standard)

    def test_patch_applied_before_integration(self):
        for config, jo in JOS.items():
            with self.subTest(config=config):
                text = jo.read_text()
                self.assertLess(
                    text.index('subprocess.check_call(command)'),
                    text.index('generate(process_dir=process_dir, runArgs=runArgs,')
                )
                self.assertIn('command + ["--dry-run"]', text)
                self.assertIn("FXFX_PR426_EXCLUSIVE_KT_VERIFIED", text)
                self.assertIn("grid_pack=GRIDPACK_MODE", text)
                self.assertIn("gridpack_compile=RECOMPILE_GRIDPACK", text)

    def test_pmg_pdf_scale_recipe_preserved_but_not_the_focus(self):
        for config, jo in JOS.items():
            with self.subTest(config=config):
                text = jo.read_text()
                self.assertIn('MG.MADGRAPH_PDFSETTING = {', text)
                self.assertIn('"central_pdf": 325100', text)
                self.assertIn('"pdf_variations": [325100, 93300]', text)
                self.assertIn('"store_rwgt_info": not GRIDPACK_MODE', text)

    def test_shower_runner_isolated_for_each_configuration(self):
        for config, runner in RUNNERS.items():
            with self.subTest(config=config):
                text = runner.read_text()
                dsid = "999998" if config == "standard111" else "999997"
                self.assertIn(f'jo="$repo/tests/2jet/{dsid}"', text)
                self.assertIn('export GRIDPACK_RECOMPILE=1', text)
                self.assertIn("evnt_count_verified.txt", text)
                self.assertIn("EVNT_EVENT_COUNT_PASS", text)
                self.assertIn("GRIDPACK_LHE_PYTHIA8_SMOKE_PASS", text)
        self.assertIn('zee2jet.EVNT.pool.root', RUNNERS["standard111"].read_text())
        self.assertIn('zee2jet_delta111.EVNT.pool.root',
                      RUNNERS["delta111"].read_text())


if __name__ == "__main__":
    unittest.main()
