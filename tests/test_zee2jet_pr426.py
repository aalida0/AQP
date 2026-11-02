"""Static guards for main-source Zee HT2 + PR426 FxFx standard111/Delta111."""
import ast
import hashlib
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "tests" / "2jet"
CONFIGS = {
    "standard111": {
        "dir": ROOT / "999998",
        "jo": "mc.aMCPy8EG_Zee_FxFx_2jets_DRjj_PR426.py",
        "runner": REPO / "scripts" / "validate_zee2jet_pr426_gridpack.sh",
    },
    "delta111": {
        "dir": ROOT / "999997",
        "jo": "mc.aMCPy8EG_Zee_FxFx_2jets_DRjj_PR426_delta111.py",
        "runner": REPO / "scripts" / "validate_zee2jet_pr426_delta111_gridpack.sh",
    },
}

# From main JOs/V+jets/Z+jets/Z(ee)/standard111/100000/REQUIRED_FILES.md
SOURCE_SHA256 = {
    "dummy_fct.f": "76f47c8fdfacd7d2136f13e5261765ab27aae21752448cae0cb4d05120e9fc08",
    "montecarlocounter_MINE.f": "fee80cac03c15fc5e7b85c791dbb4f7b284fb004faec47b2e3c6a33c9a861f0a",
}


def read_jo(cfg):
    desc = CONFIGS[cfg]
    return (desc["dir"] / desc["jo"]).read_text()


def top_level_constants(source):
    tree = ast.parse(source)
    return {
        node.targets[0].id: node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and isinstance(node.value, ast.Constant)
    }


class ZeePR426IntegrationSmokeTests(unittest.TestCase):
    def test_authoritative_main_fortran_files_bit_identical(self):
        for label, desc in CONFIGS.items():
            for filename, sha in SOURCE_SHA256.items():
                with self.subTest(label=label, filename=filename):
                    source = (desc["dir"] / filename).read_bytes()
                    self.assertEqual(hashlib.sha256(source).hexdigest(), sha)

    def test_ht2_bias_is_active_not_commented_out(self):
        for label, desc in CONFIGS.items():
            with self.subTest(label=label):
                source = (desc["dir"] / "dummy_fct.f").read_text()
                self.assertIn("subroutine bias_weight_function", source)
                self.assertIn("bias_wgt=H_T**2", source)
                jo = read_jo(label)
                self.assertIn('"event_norm": "bias"', jo)
                self.assertIn('("dummy_fct.f", "dummy_fct.f")', jo)
                self.assertIn("ZEE_HT2_BIAS_AND_DELTA_TOLERANCE_VERIFIED", jo)

    def test_sudakov_100_epsilon_tolerance_source_installed(self):
        for label, desc in CONFIGS.items():
            with self.subTest(label=label):
                src = (desc["dir"] / "montecarlocounter_MINE.f").read_text()
                self.assertIn("eps = 100.d0 * epsilon(1.d0)", src)
                self.assertIn("if(probne.gt.1.d0+eps)then", src)
                self.assertIn("if(probne.gt.1.d0) probne=1.d0", src)
                self.assertIn(
                    '("montecarlocounter_MINE.f", "montecarlocounter.f")',
                    read_jo(label),
                )

    def test_fxfx_patch_matches_canonical_main_and_is_applied(self):
        main_patch = (
            REPO / "JOs" / "V+jets" / "Z+jets" / "Z(ee)" /
            "standard111" / "100000" / "fxfx_exclusive_kt.patch"
        )
        prior_test_patch = (
            REPO / "tests" / "1jet" / "999999" / "fxfx_exclusive_kt.patch"
        )
        expected = main_patch if main_patch.exists() else prior_test_patch
        self.assertTrue(expected.exists())
        for label, desc in CONFIGS.items():
            with self.subTest(label=label):
                patch = (desc["dir"] / "fxfx_exclusive_kt.patch").read_bytes()
                self.assertEqual(patch, expected.read_bytes())
                jo = read_jo(label)
                self.assertIn('command + ["--dry-run"]', jo)
                self.assertIn("FXFX_PR426_EXCLUSIVE_KT_VERIFIED", jo)
                self.assertIn(
                    "amcatnlo_fastjetdmergemax(nQCD-2).lt.ptj**2", jo
                )
                self.assertLess(jo.index("subprocess.check_call(command)"),
                                jo.index("generate(required_accuracy="))

    def test_both_jos_have_same_integration_and_shower_settings(self):
        for label in CONFIGS:
            with self.subTest(label=label):
                jo = read_jo(label)
                settings = top_level_constants(jo)
                self.assertEqual(settings["USE_DELTA"], label == "delta111")
                self.assertEqual(settings["FOLDING"], "1, 1, 1")
                self.assertEqual(settings["REQUIRED_ACCURACY"], 0.5)
                self.assertIn("generate p p > e+ e- [QCD] @0", jo)
                self.assertIn("add process p p > e+ e- j [QCD] @1", jo)
                self.assertIn("add process p p > e+ e- j j [QCD] @2", jo)
                self.assertIn('"ptj": 8', jo)
                self.assertIn('"ickkw": 3', jo)
                self.assertIn('"mcatnlo_delta": USE_DELTA', jo)
                self.assertIn('"folding": FOLDING', jo)
                self.assertIn('"req_acc": REQUIRED_ACCURACY', jo)
                self.assertIn("PYTHIA8_nJetMax = 2", jo)
                self.assertIn("PYTHIA8_qCut = 20.0", jo)
                self.assertIn("gridpack_compile=RECOMPILE_GRIDPACK", jo)

    def test_standard_and_delta_jos_only_differ_in_mode_and_label(self):
        std = read_jo("standard111")
        delta = read_jo("delta111")
        normalized = delta.replace("USE_DELTA = True", "USE_DELTA = False")
        normalized = normalized.replace(
            "HT2 PR426 delta111 reqacc0p5",
            "HT2 PR426 standard111 reqacc0p5",
        )
        self.assertEqual(std, normalized)

    def test_delta_madgraph_pythia8_dependency(self):
        delta = read_jo("delta111")
        self.assertIn('pythia8_path = os.getenv("PY8PATH")', delta)
        self.assertIn('"lib", "libpythia8.a"', delta)
        self.assertIn('config_settings["pythia8_path"] = pythia8_path', delta)

    def test_no_pdf_reweighting_in_gridpack_mode(self):
        for label in CONFIGS:
            with self.subTest(label=label):
                jo = read_jo(label)
                self.assertIn('"pdf_variations": [] if GRIDPACK_MODE', jo)
                self.assertIn('"scale_variations": [] if GRIDPACK_MODE', jo)
                self.assertIn('"store_rwgt_info": not GRIDPACK_MODE', jo)

    def test_isolated_evnt_validation_runners(self):
        for label, desc in CONFIGS.items():
            with self.subTest(label=label):
                runner = desc["runner"].read_text()
                self.assertIn(
                    'jo="$repo/tests/2jet/' +
                    desc["dir"].name + '"', runner
                )
                self.assertIn('export GRIDPACK_RECOMPILE=1', runner)
                self.assertIn("EVNT_EVENT_COUNT_PASS", runner)
                self.assertIn("GRIDPACK_LHE_PYTHIA8_SMOKE_PASS", runner)


if __name__ == "__main__":
    unittest.main()
