"""Exact one-jet derivation and physics settings for Zee and inclusive Wenu."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CASES = (
    ("910101", "JOs/V+jets/Z+jets/Z(ee)/delta111/100001/mc.aMCPy8EG_Zee_FxFx_2jets_HT2_delta111.py",
     "mc.aMCPy8EG_Zee_FxFx_1jet_HT2_delta111_smoke.py", "Zee"),
    ("910102", "JOs/V+jets/W+jets/W(ev)/delta111/200001/mc.aMCPy8EG_Wenu_FxFx_2jets_HT2_delta111.py",
     "mc.aMCPy8EG_Wenu_FxFx_1jet_HT2_delta111_smoke.py", "Wenu"),
)

def normalized(text):
    tree = ast.parse(text)
    tree.body = [node for node in tree.body if not (
        isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Attribute)
                and ast.unparse(t) == "evgenConfig.description"
                for t in node.targets))]
    return ast.dump(tree, include_attributes=False)

class SmokeParities(unittest.TestCase):
    def test_only_multiplicity_accuracy_njetmax_and_description_change(self):
        for dsid, origin, filename, channel in CASES:
            with self.subTest(dsid=dsid):
                parent = (ROOT / origin).read_text()
                child = (ROOT / "tests/1jet" / dsid / filename).read_text()
                process_lines = [
                    s for s in parent.splitlines()
                    if s.startswith("    add process p p >") and s.endswith("@2")
                ]
                self.assertEqual(len(process_lines), 1)
                expected = parent.replace(process_lines[0] + "\n", "")
                expected = expected.replace(
                    "REQUIRED_ACCURACY = 1e-3  # Requested 2-jet integration target; physics validation pending",
                    "REQUIRED_ACCURACY = 0.5  # Smoke only; not for precision physics"
                )
                expected = expected.replace("PYTHIA8_nJetMax = 2", "PYTHIA8_nJetMax = 1")
                self.assertEqual(normalized(expected), normalized(child))
                self.assertNotIn("custom_fcts", child)  # keep unchanged as requested
                self.assertIn('"store_rwgt_info": True', child)
                if channel == "Wenu":
                    self.assertIn("generate p p > e nu [QCD] @0", child)
                    self.assertIn('    "etaj": -1.0,', child)
                else:
                    self.assertIn("generate p p > e+ e- [QCD] @0", child)
                    self.assertIn('    "mll": 40,', child)

    def test_local_auxiliaries_match_parent(self):
        for dsid, origin, _, _ in CASES:
            for name in ("dummy_fct.f", "montecarlocounter_MINE.f", "fxfx_exclusive_kt.patch"):
                with self.subTest(dsid=dsid, name=name):
                    old = (ROOT / origin).parent / name
                    new = ROOT / "tests/1jet" / dsid / name
                    self.assertEqual(old.read_bytes(), new.read_bytes())
