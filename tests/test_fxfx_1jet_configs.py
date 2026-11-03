"""Static 0+1j smoke-JO parity checks against the corresponding main JOs."""
import ast
import hashlib
import re
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = (
    ('910001', 'JOs/V+jets/Z+jets/Z(ee)/delta111/100001/mc.aMCPy8EG_Zee_FxFx_2jets_HT2_delta111.py', 'mc.aMCPy8EG_Zee_FxFx_1jet_delta111.py', True),
    ('910002', 'JOs/V+jets/W+jets/W(ev)/delta111/200001/mc.aMCPy8EG_Wenu_FxFx_2jets_HT2_delta111.py', 'mc.aMCPy8EG_Wenu_FxFx_1jet_delta111.py', True),
    ('910003', 'JOs/VV+jets/WW/os/delta111/300011/mc.aMCPy8EG_osWW_lvlv_FxFx_2jets_delta111.py', 'mc.aMCPy8EG_osWW_lvlv_FxFx_1jet_delta111.py', False),
    ('910004', 'JOs/VV+jets/WZ/lllnu/delta111/300012/mc.aMCPy8EG_WZ_lllnu_FxFx_2jets_delta111.py', 'mc.aMCPy8EG_WZ_lllnu_FxFx_1jet_delta111.py', False),
    ('910005', 'JOs/VV+jets/ZZ/llll/delta111/300013/mc.aMCPy8EG_ZZ_llll_FxFx_2jets_delta111.py', 'mc.aMCPy8EG_ZZ_llll_FxFx_1jet_delta111.py', False),
    ('910006', 'JOs/VV+jets/ZZ/llvv/delta111/300014/mc.aMCPy8EG_ZZ_llvv_FxFx_2jets_delta111.py', 'mc.aMCPy8EG_ZZ_llvv_FxFx_1jet_delta111.py', False),
)

def physics_ast(code):
    tree = ast.parse(code)
    tree.body = [node for node in tree.body if not (
        isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Attribute) and ast.unparse(target) == 'evgenConfig.description'
            for target in node.targets))]
    return ast.dump(tree, include_attributes=False)

class OneJetParityTests(unittest.TestCase):
    def test_derivation_from_full_multiplicity(self):
        for dsid, reference, filename, _ in SAMPLES:
            with self.subTest(dsid=dsid):
                src = (ROOT / reference).read_text()
                alt = (ROOT / 'tests' / '1jet' / dsid / filename).read_text()
                expected = re.sub(r'(?m)^REQUIRED_ACCURACY = (?:1e-4|1e-3)',
                                  'REQUIRED_ACCURACY = 0.5', src)
                expected, n = re.subn(r'(?m)^    add process [^\n]+ @2\n', '', expected)
                self.assertEqual(n, 1)
                expected = expected.replace('PYTHIA8_nJetMax = 2', 'PYTHIA8_nJetMax = 1')
                self.assertEqual(physics_ast(expected), physics_ast(alt))
                for value in ('"store_rwgt_info": True', 'gridpack_compile=False',
                              '[325100, 93300]', '331500',
                              'USE_DELTA = True', 'FOLDING = "1, 1, 1"'):
                    self.assertIn(value, alt)
                self.assertNotIn('@2', alt)

    def test_auxiliary_sources_identical(self):
        for dsid, reference, _, ht2 in SAMPLES:
            src = ROOT / reference
            for name in ('montecarlocounter_MINE.f', 'fxfx_exclusive_kt.patch') + (
                    ('dummy_fct.f',) if ht2 else ()):
                with self.subTest(dsid=dsid, file=name):
                    sample = ROOT / 'tests' / '1jet' / dsid / name
                    self.assertEqual(hashlib.sha256((src.parent / name).read_bytes()).digest(),
                                     hashlib.sha256(sample.read_bytes()).digest())

    def test_unique_joboptions(self):
        for dsid, _, name, _ in SAMPLES:
            d = ROOT / 'tests' / '1jet' / dsid
            self.assertEqual(list(d.glob('mc.*.py')), [d / name])

if __name__ == '__main__':
    unittest.main()
