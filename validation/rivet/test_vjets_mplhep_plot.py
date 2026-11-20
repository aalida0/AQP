"""Regression checks for the AQP mplhep plotting inputs and ratios."""
import ast
import importlib.util
from pathlib import Path
import tempfile
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("aqp_vjets_mplhep_plot",
                                            ROOT / "aqp_vjets_mplhep_plot.py")
PLOT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PLOT)


class MplhepPlotTests(unittest.TestCase):
    def test_physics_labels_and_difference_for_asymmetry(self):
        self.assertEqual(PLOT.PLOT_LABELS, {
            "S111": "MC@NLO, 111", "D111": "MC@NLO-Δ, 111",
            "D221": "MC@NLO-Δ, 221", "D441": "MC@NLO-Δ, 441",
        })
        curves = {
            "S111": (np.array([0., .4, -.2]), None),
            "D111": (np.array([.1, .5, -.1]), None),
            "D221": (np.array([.2, .6, 0.]), None),
            "D441": (np.array([.3, .7, .1]), None),
        }
        values, baseline = PLOT.ratio_values(curves, "derived_ratio_unscaled")
        self.assertEqual(baseline, 0.)
        np.testing.assert_allclose(values["D111"], [.1, .1, .1])

    def test_ordinary_ratio_masks_empty_bins(self):
        curves = {
            "S111": (np.array([4., 2., 0., .001]), None),
            "D111": (np.array([4., 0., 3., 0.]), None),
            "D221": (np.array([4., 3., 0., 0.]), None),
            "D441": (np.array([4., 2., 0., .001]), None),
        }
        values, baseline = PLOT.ratio_values(curves, "unit_integral")
        self.assertEqual(baseline, 1.)
        self.assertAlmostEqual(values["D111"][0], 1.)
        self.assertTrue(np.isnan(values["D111"][1]))
        self.assertTrue(np.isnan(values["D111"][2]))
        self.assertTrue(np.isnan(values["D111"][3]))

    def test_metadata_parser_never_executes_plot_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "jet_HT.py"
            path.write_text(
                'ax_xLabel = "Jet H_T [GeV]"\n'
                'ax_xScale = "log"\n'
                'import os; os.system("false")\n'
            )
            meta = PLOT.plot_metadata(path)
            self.assertEqual(meta["ax_xLabel"], "Jet H_T [GeV]")
            self.assertEqual(meta["ax_xScale"], "log")


if __name__ == "__main__":
    unittest.main()
