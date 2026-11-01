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
        self.assertIn("MGC.MADGRAPH_PDFSETTING = MG.MADGRAPH_PDFSETTING", source)
        self.assertIn("mgc = MGControl()", source)
        # Check the AST rather than comments: the unsupported syntax may
        # legitimately be mentioned in the JobOption documentation.
        constructors = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "MGControl"
        ]
        self.assertEqual(len(constructors), 1)
        self.assertEqual(constructors[0].args, [])
        self.assertEqual(constructors[0].keywords, [])

    def test_nlo_gridpack_generation_keeps_reweight_metadata(self):
        source = JO.read_text()
        tree = ast.parse(source, filename=str(JO))
        modify_calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "modify_run_card"
        ]
        self.assertEqual(len(modify_calls), 1)
        settings = next(
            kw.value for kw in modify_calls[0].keywords
            if kw.arg == "settings"
        )
        self.assertIsInstance(settings, ast.Dict)
        values = {
            key.value: value
            for key, value in zip(settings.keys, settings.values)
            if isinstance(key, ast.Constant) and isinstance(key.value, str)
        }
        self.assertIn("store_rwgt_info", values)
        value = values["store_rwgt_info"]
        self.assertIsInstance(value, ast.UnaryOp)
        self.assertIsInstance(value.op, ast.Not)
        self.assertIsInstance(value.operand, ast.Name)
        self.assertEqual(value.operand.id, "GRIDPACK_MODE")

    def test_recompile_is_opt_in_and_only_for_gridpack_consumption(self):
        source = JO.read_text()
        tree = ast.parse(source, filename=str(JO))
        self.assertIn('os.environ.get("GRIDPACK_RECOMPILE", "0")', source)
        self.assertIn('RECOMPILE_GRIDPACK = (recompile_setting == "1") and not GRIDPACK_MODE',
                      source)
        generate_calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "generate"
        ]
        self.assertEqual(len(generate_calls), 1)
        parameters = {keyword.arg: keyword.value
                      for keyword in generate_calls[0].keywords}
        self.assertIn("gridpack_compile", parameters)
        self.assertIsInstance(parameters["gridpack_compile"], ast.Name)
        self.assertEqual(parameters["gridpack_compile"].id, "RECOMPILE_GRIDPACK")

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
