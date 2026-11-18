"""Minimal regression tests for the V+jets plot-export audit."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("plotter", HERE / "aqp_vjets_normalized_plot.py")
plotter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plotter)


class PlotAuditTests(unittest.TestCase):
    def test_legend_labels(self):
        self.assertEqual(plotter.PLOT_LABELS, {
            "S111": "MC@NLO, 111",
            "D111": "MC@NLO-Δ, 111",
            "D221": "MC@NLO-Δ, 221",
            "D441": "MC@NLO-Δ, 441",
        })

    def test_normalization_and_shape_distance(self):
        edges = np.array([0., 1., 3.])
        sample = {label: (np.array([2., 1.]), np.array([[0.2, 0.1], [0.2, 0.1]]))
                  for label in plotter.CONFIGS}
        scaled, factors = plotter.normalize(edges, sample, "unit_integral")
        self.assertEqual(set(scaled), set(plotter.CONFIGS))
        for label in plotter.CONFIGS:
            self.assertAlmostEqual(factors[label], 4.)
            self.assertAlmostEqual(float(np.dot(scaled[label][0], np.diff(edges))), 1.)
        _, untouched = plotter.normalize(edges, sample, "derived_ratio_unscaled")
        self.assertTrue(all(factor == 1. for factor in untouched.values()))

    def test_parse_literals_without_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "plot__data.py"
            labels = ["plot_"+name+"_file.yoda.gz" for name in plotter.CONFIGS]
            obj = {name: [0, 1, 3] for name in labels}
            y = {name: [2, 1] for name in labels}
            e = {name: [[0.2, 0.1], [0.2, 0.1]] for name in labels}
            file.write_text(f"xedges = {obj!r}\nyvals = {y!r}\nyerrs = {e!r}\n")
            edges, curves = plotter.read_export(file)
            self.assertEqual(len(edges), 3)
            self.assertEqual(len(curves), 4)
            file.write_text("xedges = __import__('os').system('false')\n"
                            f"yvals = {y!r}\nyerrs = {e!r}\n")
            with self.assertRaises(ValueError):
                plotter.read_export(file)


    def test_derived_undefined_bins_are_gaps(self):
        # Rivet jet_multi_ratio: finite y but undefined error in the final bin.
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "jet_multi_ratio__data.py"
            keys = ["plot_"+label+"_file.yoda.gz" for label in plotter.CONFIGS]
            edges = {key: [0, 1, 2, 3] for key in keys}
            vals = {key: [0.3, 0.4, 0.] for key in keys}
            errors = {key: [[0.01, 0.02, float("nan")],
                            [0.01, 0.02, float("nan")]] for key in keys}
            file.write_text(f"xedges = {edges!r}\nyvals = {vals!r}\nyerrs = {errors!r}\n")
            bins, curves = plotter.read_export(file)
            for y, err in curves.values():
                self.assertTrue(np.isnan(y[-1]))
                self.assertTrue(np.isnan(err[:, -1]).all())
                self.assertAlmostEqual(y[0], 0.3)
            scaled, factors = plotter.normalize(bins, curves, "derived_ratio_unscaled")
            self.assertTrue(all(factor == 1. for factor in factors.values()))
            target = Path(temp) / "jet_multi_ratio.png"
            plotter.draw(bins, scaled, "derived_ratio_unscaled", "Zee/MC_ZJETS/jet_multi_ratio", target)
            self.assertGreater(target.stat().st_size, 0)

    def test_nan_in_differential_histogram_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "Z_pT__data.py"
            keys = ["plot_"+label+"_file.yoda.gz" for label in plotter.CONFIGS]
            edges = {key: [0, 1, 2] for key in keys}
            vals = {key: [0.5, float("nan")] for key in keys}
            errors = {key: [[0.01, float("nan")], [0.01, float("nan")]] for key in keys}
            file.write_text(f"xedges = {edges!r}\nyvals = {vals!r}\nyerrs = {errors!r}\n")
            with self.assertRaisesRegex(ValueError, "nonfinite histogram in a physical distribution"):
                plotter.read_export(file)


if __name__ == "__main__":
    unittest.main()
