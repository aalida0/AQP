"""Controlled one-variable A/B test: store NLO reweight metadata at gridpack build.

Purely static; source-parity tests do not imply successful MadGraph compilation.
"""
import ast
import hashlib
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CONTROL_DIR = ROOT / "tests/1jet/999996"
VARIANT_DIR = ROOT / "tests/1jet/999995"
CONTROL = CONTROL_DIR / "mc.aMCPy8EG_Zee_FxFx_1jet_DRjj_PR426_delta111.py"
VARIANT = VARIANT_DIR / "mc.aMCPy8EG_Zee_FxFx_1jet_DRjj_PR426_delta111_rwgt.py"
AUX = ("dummy_fct.f", "montecarlocounter_MINE.f", "fxfx_exclusive_kt.patch")
SCRIPT = ROOT / "scripts/validate_zee1jet_rwgtgridpack.sh"


def semantic_lines(source):
    """Ignore explanatory comments/description while checking executable parity."""
    return [
        line.strip()
        for line in source.splitlines()
        if line.strip()
        and not line.lstrip().startswith("#")
        and not line.lstrip().startswith("evgenConfig.description")
    ]


class ReweightGridpackJoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.control = CONTROL.read_text()
        cls.variant = VARIANT.read_text()
        cls.tree = ast.parse(cls.variant, filename=str(VARIANT))

    def test_only_one_physics_affecting_change(self):
        expected = [
            '"store_rwgt_info": True,'
            if line == '"store_rwgt_info": not GRIDPACK_MODE,' else line
            for line in semantic_lines(self.control)
        ]
        self.assertIn('"store_rwgt_info": not GRIDPACK_MODE,',
                      semantic_lines(self.control))
        self.assertEqual(semantic_lines(self.variant), expected)

    def test_nlo_metadata_always_true_in_run_card(self):
        functions = [
            n for n in ast.walk(self.tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "modify_run_card"
        ]
        self.assertEqual(len(functions), 1)
        settings = next(k.value for k in functions[0].keywords
                        if k.arg == "settings")
        self.assertIsInstance(settings, ast.Dict)
        values = {
            k.value: v for k, v in zip(settings.keys, settings.values)
            if isinstance(k, ast.Constant) and isinstance(k.value, str)
        }
        self.assertIsInstance(values['store_rwgt_info'], ast.Constant)
        self.assertIs(values['store_rwgt_info'].value, True)
        self.assertIsInstance(values['mcatnlo_delta'], ast.Name)
        self.assertEqual(values['mcatnlo_delta'].id, 'USE_DELTA')

    def test_no_new_process_changes_and_distinct_name(self):
        files = list(VARIANT_DIR.glob("mc.*.py"))
        self.assertEqual(files, [VARIANT])
        self.assertIn("generate p p > e+ e- [QCD] @0", self.variant)
        self.assertIn("add process p p > e+ e- j [QCD] @1", self.variant)
        self.assertNotIn("add process p p > e+ e- j j [QCD] @2", self.variant)
        self.assertIn("PYTHIA8_nJetMax = 1", self.variant)
        self.assertIn("FOLDING = \"1, 1, 1\"", self.variant)
        self.assertIn('RECOMPILE_GRIDPACK = (recompile_setting == "1") and not GRIDPACK_MODE',
                      self.variant)
        self.assertIn("USE_DELTA = True", self.variant)
        self.assertNotIn("AQP", self.variant)

    def test_auxiliary_files_byte_identical_to_proven_control(self):
        for name in AUX:
            with self.subTest(name=name):
                self.assertEqual(
                    hashlib.sha256((VARIANT_DIR/name).read_bytes()).hexdigest(),
                    hashlib.sha256((CONTROL_DIR/name).read_bytes()).hexdigest()
                )

    def test_validation_script_targets_variant_and_no_recompile_by_default(self):
        script = SCRIPT.read_text()
        self.assertIn('jo="$repo/tests/1jet/999995"', script)
        self.assertIn("export GRIDPACK_RECOMPILE=0", script)
        self.assertIn("export GRIDPACK_RECOMPILE=1", script)
        self.assertIn('mktemp -d', script)
        self.assertIn("EVNT_EVENT_COUNT_PASS", script)
        self.assertIn("summarize_zee1jet_validation.py", script)


if __name__ == "__main__":
    unittest.main()
