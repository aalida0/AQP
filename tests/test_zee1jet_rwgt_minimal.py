"""Regression tests for the minimized Zee 0+1j Delta111 rwgt gridpack JO.

The 999995 JO has generated a valid 20-event EVNT without recompilation.
The 999994 variant must preserve its physics settings, sources and Pythia8.
These are static checks, not an Athena or gridpack-creation test.
"""
import ast
import hashlib
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "tests/1jet/999995"
MIN = ROOT / "tests/1jet/999994"
NAME = "mc.aMCPy8EG_Zee_FxFx_1jet_DRjj_PR426_delta111_rwgt.py"
AUX = ("dummy_fct.f", "montecarlocounter_MINE.f", "fxfx_exclusive_kt.patch")


def assignment(tree, target):
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(ast.unparse(t) == target for t in targets):
                return node.value
    raise AssertionError("Missing assignment " + target)


def only_call(tree, name):
    matches = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call) and ast.unparse(n.func) == name
    ]
    if len(matches) != 1:
        raise AssertionError("Expected exactly one call to %s (got %d)" % (name, len(matches)))
    return matches[0]


def keyword(call, name):
    return next(k.value for k in call.keywords if k.arg == name)


def equivalent(a, b):
    return ast.dump(a, include_attributes=False) == ast.dump(b, include_attributes=False)


class MinimalOneJetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (REF / NAME).read_text()
        cls.minimal = (MIN / NAME).read_text()
        cls.a = ast.parse(cls.original)
        cls.b = ast.parse(cls.minimal)

    def test_jo_is_standalone_and_has_same_physics_constants(self):
        self.assertEqual(list(MIN.glob("mc.*.py")), [MIN / NAME])
        self.assertNotIn("AQP", self.minimal)
        for name in ("USE_DELTA", "FOLDING", "REQUIRED_ACCURACY", "GRIDPACK_MODE",
                     "evgenConfig.nEventsPerJob", "evgenConfig.generators",
                     "evgenConfig.keywords", "evgenConfig.contact"):
            with self.subTest(name=name):
                self.assertTrue(equivalent(assignment(self.a, name),
                                           assignment(self.b, name)), name)

    def test_same_madgraph_process_and_other_settings(self):
        for name in ("process", "MGC.MADGRAPH_PDFSETTING",
                     "beam_energy", "nevents", "config_settings"):
            with self.subTest(name=name):
                self.assertTrue(equivalent(assignment(self.a, name),
                                           assignment(self.b, name)), name)

    def test_full_pmg_pdf_recipe_in_event_generation(self):
        # The existing 999999 one-jet JO defines the full PMG recipe.
        official = (ROOT / "tests/1jet/999999/mc.aMCPy8EG_Zee_FxFx_1jet_smoke.py")
        official_tree = ast.parse(official.read_text())
        full_pmg = ast.literal_eval(
            assignment(official_tree, "MG.MADGRAPH_PDFSETTING")
        )
        minimal_dict = assignment(self.b, "MG.MADGRAPH_PDFSETTING")
        self.assertIsInstance(minimal_dict, ast.Dict)

        def mode_settings(gridpack_mode):
            result = {}
            for key, val in zip(minimal_dict.keys, minimal_dict.values):
                if isinstance(val, ast.IfExp):
                    self.assertEqual(ast.unparse(val.test), "GRIDPACK_MODE")
                    val = val.body if gridpack_mode else val.orelse
                result[ast.literal_eval(key)] = ast.literal_eval(val)
            return result

        self.assertEqual(mode_settings(False), full_pmg)
        self.assertEqual(full_pmg["pdf_variations"], [325100, 93300])
        self.assertEqual(full_pmg["alternative_pdfs"], [
            304400, 13000, 25300, 14000, 14100, 14200, 61200,
            42560, 303200, 27400, 331500,
        ])
        self.assertEqual(full_pmg["scale_variations"], [0.5, 1, 2])
        self.assertEqual(mode_settings(True), {
            "central_pdf": 325100,
            "pdf_variations": [],
            "alternative_pdfs": [],
            "scale_variations": [],
        })

    def test_identical_run_card_and_generation_arguments(self):
        for name in ("modify_run_card", "modify_config_card", "arrange_output"):
            with self.subTest(name=name):
                self.assertTrue(equivalent(only_call(self.a, name),
                                           only_call(self.b, name)), name)
        generate_ref = only_call(self.a, "generate")
        generate_min = only_call(self.b, "generate")
        original_keys = {k.arg: k.value for k in generate_ref.keywords}
        minimal_keys = {k.arg: k.value for k in generate_min.keywords}
        self.assertEqual(original_keys.keys(), minimal_keys.keys())
        for name in original_keys:
            if name == "gridpack_compile":
                self.assertIsInstance(minimal_keys[name], ast.Constant)
                self.assertIs(minimal_keys[name].value, False)
                self.assertEqual(ast.unparse(original_keys[name]),
                                 "RECOMPILE_GRIDPACK")
            else:
                with self.subTest(key=name):
                    self.assertTrue(equivalent(original_keys[name],
                                               minimal_keys[name]))
        self.assertIn('"store_rwgt_info": True', self.minimal)

    def test_auxiliaries_identical_and_patched_during_gridpack_mode(self):
        for name in AUX:
            with self.subTest(name=name):
                self.assertEqual(
                    hashlib.sha256((MIN/name).read_bytes()).digest(),
                    hashlib.sha256((REF/name).read_bytes()).digest())
        for literal in (
            '("dummy_fct.f", "dummy_fct.f")',
            '("montecarlocounter_MINE.f", "montecarlocounter.f")',
            'patch_name = "fxfx_exclusive_kt.patch"',
            'command + ["--dry-run"]',
            'subprocess.check_call(command)',
        ):
            self.assertIn(literal, self.minimal)

    def test_pythia8_fxfx_and_no_recompile(self):
        for literal in (
            'PYTHIA8_nJetMax = 1', 'PYTHIA8_qCut = 20.0',
            'include("Pythia8_i/Pythia8_A14_NNPDF23LO_EvtGen_Common.py")',
            'include("Pythia8_i/Pythia8_aMcAtNlo.py")',
            'include("Pythia8_i/Pythia8_FxFx_A14mod.py")'
        ):
            self.assertIn(literal, self.minimal)
        self.assertIn('gridpack_compile=False', self.minimal)
        self.assertNotIn('GRIDPACK_RECOMPILE', self.minimal)

    def test_validator_is_isolated_and_checks_20_evnt_events(self):
        script = (ROOT / "scripts/validate_zee1jet_rwgt_min.sh").read_text()
        self.assertIn('jo="$repo/tests/1jet/999994"', script)
        self.assertIn("export GRIDPACK_RECOMPILE=0", script)
        self.assertIn('mktemp -d "$base/zee1jet_rwgt_min.norecompile.XXXXXXXX"', script)
        self.assertIn('EVNT_EVENT_COUNT_PASS', script)
        self.assertIn('summarize_zee1jet_validation.py', script)


if __name__ == "__main__":
    unittest.main()
