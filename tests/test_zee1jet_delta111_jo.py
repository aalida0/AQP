"""Static checks for the independent Zee 0+1j FxFx MC@NLO-Delta smoke JO.

Does not run MadGraph, Condor, Gen_tf or modify a gridpack.
"""
import ast
import hashlib
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]
DIR = REPO / "tests" / "1jet" / "999996"
JO = DIR / "mc.aMCPy8EG_Zee_FxFx_1jet_DRjj_PR426_delta111.py"
TWOJET = REPO / "tests" / "2jet" / "999997"
AUX = ("dummy_fct.f", "montecarlocounter_MINE.f", "fxfx_exclusive_kt.patch")


class OneJetDeltaJOTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = JO.read_text()
        cls.tree = ast.parse(cls.source, filename=str(JO))

    def test_new_dsid_contains_one_complete_jo(self):
        self.assertEqual(list(DIR.glob("mc.*.py")), [JO])
        self.assertNotIn("AQP", self.source)

    def test_new_jo_is_minimal_derivation_of_successful_two_jet_jo(self):
        """No functional changes besides dropping @2 and adapting Py8 nJetMax."""
        twojet_jo = TWOJET / "mc.aMCPy8EG_Zee_FxFx_2jets_DRjj_PR426_delta111.py"

        def semantic_lines(source):
            return [
                line.strip()
                for line in source.splitlines()
                if line.strip()
                and not line.lstrip().startswith("#")
                and not line.lstrip().startswith("evgenConfig.description")
            ]

        original = semantic_lines(twojet_jo.read_text())
        expected = [
            "PYTHIA8_nJetMax = 1" if line == "PYTHIA8_nJetMax = 2" else line
            for line in original
            if line != "add process p p > e+ e- j j [QCD] @2"
        ]
        self.assertEqual(
            semantic_lines(self.source), expected,
            "New 1j JO diverges from the two-jet Delta111 reference "
            "in additional executable configuration; review changes.",
        )

    def test_new_one_jet_fxfx_process_without_two_jet_multiplicity(self):
        self.assertIn("generate p p > e+ e- [QCD] @0", self.source)
        self.assertIn("add process p p > e+ e- j [QCD] @1", self.source)
        self.assertNotIn("add process p p > e+ e- j j [QCD] @2", self.source)
        self.assertIn("PYTHIA8_nJetMax = 1", self.source)
        self.assertIn("PYTHIA8_qCut = 20.0", self.source)
        self.assertIn("Pythia8_i/Pythia8_FxFx_A14mod.py", self.source)

    def test_matching_folding_ht2_bias_and_source_patches(self):
        for declaration in ('USE_DELTA = True', 'FOLDING = "1, 1, 1"',
                            'REQUIRED_ACCURACY = 0.5', '"event_norm": "bias"',
                            '"mcatnlo_delta": USE_DELTA',
                            '"folding": FOLDING',
                            '"store_rwgt_info": not GRIDPACK_MODE'):
            self.assertIn(declaration, self.source)
        self.assertIn('("dummy_fct.f", "dummy_fct.f")', self.source)
        self.assertIn('("montecarlocounter_MINE.f", "montecarlocounter.f")', self.source)
        self.assertIn('patch_name = "fxfx_exclusive_kt.patch"', self.source)
        for name in AUX:
            with self.subTest(name=name):
                self.assertEqual(
                    hashlib.sha256((DIR / name).read_bytes()).digest(),
                    hashlib.sha256((TWOJET / name).read_bytes()).digest(),
                    "The new 1j source must exactly match the validated 2j source",
                )

    def test_recompilation_is_event_mode_opt_in(self):
        self.assertIn('os.environ.get("GRIDPACK_RECOMPILE", "0")', self.source)
        self.assertIn('RECOMPILE_GRIDPACK = (recompile_setting == "1") and not GRIDPACK_MODE',
                      self.source)
        generate_calls = [
            n for n in ast.walk(self.tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name) and n.func.id == "generate"
        ]
        self.assertEqual(len(generate_calls), 1)
        keywords = {k.arg: k.value for k in generate_calls[0].keywords}
        self.assertIsInstance(keywords["grid_pack"], ast.Name)
        self.assertEqual(keywords["grid_pack"].id, "GRIDPACK_MODE")
        self.assertIsInstance(keywords["gridpack_compile"], ast.Name)
        self.assertEqual(keywords["gridpack_compile"].id, "RECOMPILE_GRIDPACK")

    def test_workflow_uses_archived_grids_without_reintegration(self):
        self.assertIn("GRIDPACK_MODE = not is_gen_from_gridpack()", self.source)
        self.assertIn("process_dir = str(MADGRAPH_GRIDPACK_LOCATION)", self.source)
        self.assertIn("mgc.getRunCardDict()", self.source)
        self.assertIn('{"run_mode": 0, "nb_core": 1}', self.source)
        self.assertIn('"central_pdf": 325100', self.source)

    def test_new_validator_uses_correct_dsid_and_two_independent_modes(self):
        script = (REPO / "scripts" / "validate_zee1jet_delta111_gridpack.sh").read_text()
        self.assertIn('jo="$repo/tests/1jet/999996"', script)
        self.assertIn('export GRIDPACK_RECOMPILE=0', script)
        self.assertIn('export GRIDPACK_RECOMPILE=1', script)
        self.assertIn('$(basename "$archive")', script)
        self.assertIn('mktemp -d', script)
        self.assertIn("EVNT_EVENT_COUNT_PASS", script)
        self.assertIn('summarize_zee1jet_validation.py', script)


if __name__ == "__main__":
    unittest.main()
