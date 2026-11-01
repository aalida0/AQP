"""Static regression checks for the experimental Zee 0,1-jet gridpack smoke JO."""
import ast
from pathlib import Path
import unittest


JO = (Path(__file__).resolve().parents[1] / "tests" / "1jet" / "999999"
      / "mc.aMCPy8EG_Zee_FxFx_1jet_smoke.py")


class ZeeSmokeJOTests(unittest.TestCase):
    def test_pmg_pdf_and_scale_recipe(self):
        source = JO.read_text()
        tree = ast.parse(source, filename=str(JO))
        settings = None
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            if any(isinstance(target, ast.Attribute)
                   and isinstance(target.value, ast.Name)
                   and target.value.id == "MG"
                   and target.attr == "MADGRAPH_PDFSETTING"
                   for target in node.targets):
                self.assertIsNone(settings, "PDF recipe assigned more than once")
                settings = ast.literal_eval(node.value)
        self.assertIsNotNone(settings)
        self.assertEqual(settings["central_pdf"], 325100)
        self.assertEqual(settings["pdf_variations"], [325100, 93300])
        self.assertEqual(settings["alternative_pdfs"],
                         [304400, 13000, 25300, 14000, 14100, 14200,
                          61200, 42560, 303200, 27400, 331500])
        self.assertEqual(settings["scale_variations"], [0.5, 1, 2])
        self.assertLess(source.index("MG.MADGRAPH_PDFSETTING ="),
                        source.index("mgc = MGControl("))
        self.assertIn("MGControl(pdf_setting=MG.MADGRAPH_PDFSETTING)", source)

    def test_reuse_does_not_reintegrate(self):
        source = JO.read_text()
        self.assertIn("GRIDPACK_MODE = not is_gen_from_gridpack()", source)
        self.assertIn("process_dir = str(MADGRAPH_GRIDPACK_LOCATION)", source)
        self.assertIn("grid_pack=GRIDPACK_MODE", source)
        self.assertIn("PYTHIA8_nJetMax = 1", source)
        self.assertIn("PYTHIA8_qCut = 20.0", source)
        self.assertIn("Pythia8_i/Pythia8_FxFx_A14mod.py", source)


if __name__ == "__main__":
    unittest.main()
