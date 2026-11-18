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


if __name__ == "__main__":
    unittest.main()
