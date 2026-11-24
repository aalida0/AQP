"""Regression tests: mplhep must not modify Rivet plotting physics content."""
import importlib.util
import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "aqp_vjets_mplhep_plot", ROOT / "aqp_vjets_mplhep_plot.py")
PLOT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PLOT)


def restore_style_only(styled):
    """Reverse our three visual edits to prove lossless Rivet content."""
    original = styled.replace(
        "import matplotlib.pyplot as plt\nimport mplhep as hep",
        "import matplotlib.pyplot as plt")
    original = original.replace(PLOT.ATLAS_STYLE, PLOT.STYLE_LINE)
    original = original.replace(
        "# Font is provided by mplhep ATLAS style.", PLOT.FONT_LINE)
    original = original.replace(
        "\nratio0_ax.xaxis.label.set_horizontalalignment('right')"
        "\nratio0_ax.xaxis.set_label_coords(0.96, -0.15)"
        "\nfig.subplots_adjust(right=0.94, bottom=0.16)", "")
    original = original.replace(
        "\nhep.atlas.label('Internal', data=False, ax=ax, loc=1, fontsize=11)", "")
    original = original.replace(
        "\nax.text(0.97, 0.96, r'$\\bf{ATLAS}$ Simulation Internal', "
        "ha='right', va='top', transform=ax.transAxes, fontsize=11)", "")
    # The only additional edits are the two stepped-histogram linewidths.
    # Error-bar width settings and their x/y uncertainty arrays stay untouched.
    for anchor in (PLOT.HIST_UPPER_LINE, PLOT.HIST_RATIO_LINE):
        thick = anchor.replace(
            "linewidth=styles[label]['linewidth']",
            f"linewidth={PLOT.HIST_LINE_WIDTH} * styles[label]['linewidth']")
        original = original.replace(thick, anchor)
    return original


TEMPLATE = """import matplotlib.pyplot as plt
plt.style.use(os.path.join(plotDir, '../default.mplstyle'))
plt.rc('font', family='DejaVu Sans')
labels = {'legend': (['S111', 'D111', 'D221', 'D441'], '')}
styles = {'S111': {'color': '#EE3311'}, 'D441': {'color': '#FF9900'}}
yvals = dataf['yvals']
xedges = dataf['xedges']
main_err = np.array(dataf['yerrs'][label])
ratio_err = np.array(dataf['ratio0_yerrs'][label])
ax.plot(xpos, ypos,
                       linewidth=styles[label]['linewidth'],
                       drawstyle=styles[label]['drawstyle'])
ratio0_ax.plot(xpos, ypos,
                       linewidth=styles[label]['linewidth'],
                       linestyle=styles[label]['ratio0_linestyle'])
ax.errorbar(xpoints, yvals, yerr=main_err)
ratio0_ax.errorbar(xpoints, yvals, yerr=ratio_err)
tmp[-1][0].set_linewidth(styles[label]['linewidth'])
ratio0_ax.set_ylabel('Ratio')
ax.set_xlim(xLims)
ax.set_ylim(yLims)
ax.add_artist(ax.legend(legend_items, labels['legend'][0],
                        loc='center left', bbox_to_anchor=(0.0, 0.5)))
fig.align_ylabels((ax, ratio0_ax))
# numerical __data.py is loaded by the source
"""


class MplhepPlotTests(unittest.TestCase):
    def test_restylizing_preserves_every_original_instruction(self):
        result = PLOT.restyle_script(TEMPLATE)
        self.assertEqual(restore_style_only(result), TEMPLATE)
        self.assertIn("dataf['ratio0_yerrs'][label]", result)
        self.assertIn("dataf['yerrs'][label]", result)
        self.assertIn("linewidth=1.8 * styles[label]['linewidth']", result)
        self.assertEqual(result.count("linewidth=1.8 * styles[label]['linewidth']"), 2)
        self.assertIn("tmp[-1][0].set_linewidth(styles[label]['linewidth'])", result)
        self.assertEqual(result.count("dataf['ratio0_yerrs'][label]"), 1)
        self.assertIn("'#EE3311'", result)
        self.assertIn("'#FF9900'", result)
        self.assertIn("ax.set_ylim(yLims)", result)
        self.assertIn("ax.set_xlim(xLims)", result)
        self.assertIn("labels['legend'][0]", result)
        self.assertNotIn("Unit-area density", result)
        self.assertNotIn("Shape-only diagnostic", result)
        self.assertNotIn("hep.histplot(", result)

    def test_upper_left_legend_moves_atlas_label_not_legend(self):
        original = TEMPLATE.replace(
            "loc='center left', bbox_to_anchor=(0.0, 0.5)",
            "loc='upper left', bbox_to_anchor=(0.0, 0.97)")
        result = PLOT.restyle_script(original)
        self.assertIn("loc='upper left', bbox_to_anchor=(0.0, 0.97)", result)
        self.assertIn("ax.text(0.97, 0.96,", result)
        self.assertEqual(restore_style_only(result), original)

    def test_folding_labels_are_legend_only(self):
        default = PLOT.restyle_script(TEMPLATE)
        result = PLOT.restyle_script(TEMPLATE, folding_labels=True)
        start = result.index("from matplotlib.legend import Legend\n")
        end = result.index(PLOT.LABEL_ANCHOR, start)
        self.assertEqual(result[:start] + result[end:], default)
        self.assertIn("MC@NLO, folding 111", result)
        self.assertIn("MC@NLO-Δ, folding 441", result)
        self.assertIn("ax.set_ylim(yLims)", result)

    def test_rejects_non_rivet_style_script(self):
        with self.assertRaisesRegex(ValueError, "plotting anchor"):
            PLOT.restyle_script("print('not a Rivet auto-plot')")

    def test_actual_rivet_source_preserved_when_available(self):
        source = Path(os.environ.get(
            "AQP_VJETS_SOURCE",
            "/data/aalida/AQP_Rivet_full/outputs/Vjets_final_plots_20261118"))
        if not source.is_dir():
            self.skipTest("Rivet exported plots not mounted here")
        scripts = sorted(p for p in source.glob(
            "*/01_four_way_common_MC_shapes/*/*.py")
            if not p.name.endswith("__data.py"))
        self.assertEqual(len(scripts), 101)
        for p in scripts:
            with self.subTest(path=str(p)):
                raw = p.read_text(encoding="utf-8")
                self.assertEqual(restore_style_only(PLOT.restyle_script(raw)), raw)
                self.assertTrue(p.with_name(p.stem + "__data.py").is_file())


if __name__ == "__main__":
    unittest.main()
