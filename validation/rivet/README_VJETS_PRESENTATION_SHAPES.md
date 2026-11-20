# Presentation-only V+jets normalized-shape gallery

This is a **separate presentation deliverable**, not a replacement for the
original Rivet/YODA outputs. It resolves the misleading factor-of-~2200 Zee
D441 and much larger Wenu rate-scale mismatch *for shape-comparison slides
only*. Absolute rates **remain unvalidated**.

## Method and preservation

The program `aqp_vjets_presentation_plot.py` runs each of Rivet's original
101 four-way generated plotting scripts. Data are normalized **in memory**,
after loading the original `__data.py`, without modifying the source.

- Ordinary differential histograms: divide each configuration by its own
  bin-width-weighted integral (unit-area shapes).
- Inclusive jet multiplicity: divide by the first jet-multiplicity bin.
- Precomputed asymmetries, charge ratios, and jet-multiplicity ratios:
  **do not normalize**. Preserve their original Rivet values.
- The original statistical bin errors are divided by the same scale as
  each histogram, preserving relative errors. The normalization integral
  has uncertainty and introduces covariance **not recovered here**.
- Original Rivet ratio-panel values **and ratio errors** are multiplied
  by the consistent S111/sample scale ratio, including D441.
- Four configurations retain their original bin edges, colors, legend
  text and error bars. Histogram outlines use the independently requested
  1.8× line width from the existing `aqp_vjets_mplhep_plot.py`.
- Original x-axis labels, ranges and scales remain. The y-axis retains
  **Rivet's observable-specific differential expression** rather than
  showing a generic "Unit-area normalized shape" label. For normalized
  ordinary histograms, the expression is multiplied by `1/sigma` and
  the `pb` factor is removed, e.g.
  `dσ/dη(jet 1) [pb]` -> `(1/σ) dσ/dη(jet 1)` and
  `dσ/dHT [pb/GeV]` -> `(1/σ) dσ/dHT [GeV^-1]`.
  This unit adjustment is necessary because independent area normalization
  destroys the absolute pb scale. Inclusive jet multiplicities keep the
  `σ(≥Njet)` expression but use a first-bin denominator.
  Their axes are autoscaled to normalized data.
- The `mplhep` ATLAS Simulation Internal label is placed in the standard
  **upper-left** position, inside the upper panel. The four-configuration
  legend is placed at the **upper right**, inside the axes, with names
  `MC@NLO, 111`, `MC@NLO-Δ, 111/221/441`.
  Curve colors and all original Rivet error bars remain unchanged.
- No diagnostic footer is added to figures.

## Execute on UChicago AF login node

```bash
cd ~/AQP
git pull --ff-only origin study/vjets-final-shape-audit-20261118

~/.venvs/aqp-mplhep/bin/python -m unittest discover \
  -s validation/rivet -p 'test_vjets_presentation_plot.py' -v

~/.venvs/aqp-mplhep/bin/python \
  validation/rivet/aqp_vjets_presentation_plot.py \
  --source /data/aalida/AQP_Rivet_full/outputs/Vjets_final_plots_20261118 \
  --output /data/aalida/AQP_Rivet_full/outputs/Vjets_presentation_shapes_20261120 \
  --check-only
```

The check-only call prints `PLOTS=101 ERROR_COUNT=0`; it does not
create the destination directory.

Then render by omitting `--check-only`:

```bash
~/.venvs/aqp-mplhep/bin/python \
  validation/rivet/aqp_vjets_presentation_plot.py \
  --source /data/aalida/AQP_Rivet_full/outputs/Vjets_final_plots_20261118 \
  --output /data/aalida/AQP_Rivet_full/outputs/Vjets_presentation_shapes_20261120
```

Open `Vjets_presentation_shapes_20261120/index.html`.
It contains 101 PNG and 101 PDF figures, with the exact scale factors
recorded in `normalization_manifest.csv`. All earlier raw/official
galleries are kept untouched.

## Wording for the presentation

Suggested slide caption:

**Normalized shape comparisons of MG5_aMC@NLO + Pythia8 FxFx samples
(S111, D111, D221, D441). Individual distributions are normalized to
unit area; rate normalization remains under validation.**

Do not show these curves as absolute differential cross sections,
and do not use them to conclude that folding changes the predicted rate.
The physics-relevant negative-weight-fraction and generation-cost
comparisons are independent of this plotting normalization.

This task does **not** repair the production cross-section metadata
(`CrossSection = 1.0` vs `0.0`), fix `MC_WKTSPLITTINGS` in official
Rivet, or complete the remaining ATLAS/CMS routines.
