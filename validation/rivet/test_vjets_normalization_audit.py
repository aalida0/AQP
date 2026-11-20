"""Unit tests for the read-only four-way Rivet normalization audit."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "aqp_vjets_normalization_audit", ROOT / "aqp_vjets_normalization_audit.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class NormalizationAuditTests(unittest.TestCase):
    def test_mixed_cross_section_conventions_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            parent = (Path(temp) / "Zee" /
                      "01_four_way_common_MC_shapes" / "MC_ZJETS")
            parent.mkdir(parents=True)
            (parent / "jet_HT__data.py").write_text("# dummy export\n")
            curves = {
                "S111": (np.array([0.1, 0.1]), np.zeros((2, 2))),
                "D111": (np.array([0.1, 0.1]), np.zeros((2, 2))),
                "D221": (np.array([0.1, 0.1]), np.zeros((2, 2))),
                "D441": (np.array([220., 220.]), np.zeros((2, 2))),
            }
            with patch.object(AUDIT, "ANALYSES", {"Zee": ("MC_ZJETS",)}), \
                 patch.object(AUDIT, "read_export",
                              return_value=(np.array([0., 1., 2.]), curves)):
                rows = AUDIT.audit(Path(temp))
            self.assertEqual(len(rows), 4)
            d441 = next(row for row in rows if row["config"] == "D441")
            self.assertEqual(d441["status"], "OUTLIER")
            self.assertAlmostEqual(d441["relative_to_S111"], 2200)

    def test_export_files_remain_unmodified(self):
        with tempfile.TemporaryDirectory() as temp:
            parent = (Path(temp) / "Wenu" /
                      "01_four_way_common_MC_shapes" / "MC_WJETS")
            parent.mkdir(parents=True)
            inp = parent / "jet_HT__data.py"
            inp.write_text("# original export remains unchanged\n")
            before = inp.read_bytes()
            curves = {name: (np.array([1., 2.]), np.zeros((2, 2)))
                      for name in AUDIT.CONFIGS}
            with patch.object(AUDIT, "ANALYSES", {"Wenu": ("MC_WJETS",)}), \
                 patch.object(AUDIT, "read_export",
                              return_value=(np.array([0., 1., 2.]), curves)):
                _ = AUDIT.audit(Path(temp))
            self.assertEqual(inp.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
