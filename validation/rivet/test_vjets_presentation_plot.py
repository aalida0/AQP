"""Regression tests for presentation-only V+jets shape scaling."""
import copy
import importlib.util
from pathlib import Path
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "aqp_vjets_presentation_plot", ROOT / "aqp_vjets_presentation_plot.py")
PLOT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PLOT)


def fake_export():
    names = ["Zee_S111_a", "Zee_D111_a", "Zee_D221_a", "Zee_D441_a"]
    factors = [1.0, 1.2, 0.8, 2200.0]
    edges = np.array([20.0, 25.0, 35.0])
    ys = [np.array([2.0, 1.0])*factor for factor in factors]
    return {
        "xedges": {k: edges.copy() for k in names},
        "yvals": {k: y.copy() for k, y in zip(names, ys)},
        "yerrs": {k: np.full((2, 2), 0.2*factor)
                  for k, factor in zip(names, factors)},
        "ratio0_yvals": {k: np.full(2, factor) for k, factor in zip(names, factors)},
        "ratio0_yerrs": {k: np.full((2, 2), 0.04*factor)
                         for k, factor in zip(names, factors)},
        "variation_yvals": {}, "ratio0_variation_vals": {},
    }


class PresentationTests(unittest.TestCase):
    def test_all_shapes_unit_area_even_d441(self):
        data = fake_export()
        initial = copy.deepcopy(data)
        info = PLOT.rescale_plot_data(data, "jet_HT")
        self.assertEqual(info["mode"], "unit_integral")
        for key, y in data["yvals"].items():
            self.assertAlmostEqual(
                np.dot(y, np.diff(data["xedges"][key])), 1.0)
            before = initial["yerrs"][key]
            self.assertTrue(np.allclose(data["yerrs"][key],
                                        before / info["scales"][key]))
            self.assertTrue(np.allclose(data["ratio0_yvals"][key], [1, 1]))
            self.assertTrue(np.allclose(data["ratio0_yerrs"][key],
                                        [[.04, .04], [.04, .04]]))

    def test_inclusive_jet_yield_first_bin(self):
        data = fake_export()
        info = PLOT.rescale_plot_data(data, "jet_multi_inclusive")
        self.assertEqual(info["mode"], "inclusive_jet_bin")
        for hist in data["yvals"].values():
            self.assertAlmostEqual(hist[0], 1.0)

    def test_derived_asymmetry_is_unmodified(self):
        data = fake_export()
        before = copy.deepcopy(data)
        info = PLOT.rescale_plot_data(data, "W_chargeasymm_eta")
        self.assertEqual(info["mode"], "derived_ratio_unscaled")
        for field in ("yvals", "yerrs", "ratio0_yvals", "ratio0_yerrs"):
            for key in data[field]:
                np.testing.assert_array_equal(data[field][key], before[field][key])

    def test_bad_integral_rejected(self):
        data = fake_export()
        data["yvals"]["Zee_D441_a"] *= -1
        with self.assertRaisesRegex(ValueError, "Invalid integral"):
            PLOT.rescale_plot_data(data, "jet_HT")

    def test_ylabel_preserves_rivet_observable_and_corrects_units(self):
        original_eta = r'$\mathrm{d}\sigma/\mathrm{d}\eta(\mathrm{jet~1})$ [pb]'
        self.assertEqual(
            PLOT.presentation_ylabel(original_eta, "unit_integral"),
            r'$\frac{1}{\sigma}\,\mathrm{d}\sigma/\mathrm{d}\eta(\mathrm{jet~1})
        # The source-to-source transform receives only a string; the renderer
        # executes it in-memory with the original script's __file__ preserved.
        code = (ROOT / "aqp_vjets_presentation_plot.py").read_text()
        self.assertIn("code = restyle_script(original)", code)
        self.assertIn("dataf, {script.stem!r}", code)
        self.assertNotIn(".write_text(code", code)
        self.assertIn("rescale_plot_data", code)


if __name__ == "__main__":
    unittest.main()

        )
        original_ht = r'$\mathrm{d}\sigma/\mathrm{d}HT$ [pb/GeV]'
        self.assertEqual(
            PLOT.presentation_ylabel(original_ht, "unit_integral"),
            r'$\frac{1}{\sigma}\,\mathrm{d}\sigma/\mathrm{d}HT$ [GeV$^{-1}$]'
        )
        self.assertNotIn("Unit-area normalized shape",
                         PLOT.presentation_ylabel(original_ht, "unit_integral"))

    def test_inclusive_axis_uses_first_bin_denominator(self):
        source = r'$\sigma(\geq N_{\mathrm{jet}})$ [pb]'
        result = PLOT.presentation_ylabel(source, "inclusive_jet_bin")
        self.assertIn(r'\sigma(\geq N_{\mathrm{jet}})', result)
        self.assertIn(r'/\sigma_{\mathrm{first\,bin}}', result)
        self.assertNotIn("[pb]", result)

    def test_derived_axis_and_missing_metadata_unchanged(self):
        asym = r'$(\mathrm{d}\sigma(W^+)-\mathrm{d}\sigma(W^-))
        # The source-to-source transform receives only a string; the renderer
        # executes it in-memory with the original script's __file__ preserved.
        code = (ROOT / "aqp_vjets_presentation_plot.py").read_text()
        self.assertIn("code = restyle_script(original)", code)
        self.assertIn("dataf, {script.stem!r}", code)
        self.assertNotIn(".write_text(code", code)
        self.assertIn("rescale_plot_data", code)


if __name__ == "__main__":
    unittest.main()

        self.assertEqual(PLOT.presentation_ylabel(asym, "derived_ratio_unscaled"), asym)
        self.assertEqual(PLOT.presentation_ylabel("", "unit_integral"), "")

    def test_original_script_is_not_written_to(self):
        # The source-to-source transform receives only a string; the renderer
        # executes it in-memory with the original script's __file__ preserved.
        code = (ROOT / "aqp_vjets_presentation_plot.py").read_text()
        self.assertIn("code = restyle_script(original)", code)
        self.assertIn("dataf, {script.stem!r}", code)
        self.assertNotIn(".write_text(code", code)
        self.assertIn("rescale_plot_data", code)


if __name__ == "__main__":
    unittest.main()
