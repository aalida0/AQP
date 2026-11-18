# AQP V+jets — diagnostic plot correction (November 2026)

**Status: diagnostic, not final physics validation.** This branch preserves a
reproducible correction for the **four-way S111/D111/D221/D441 shape comparison**
after a normalization mismatch was discovered in the Rivet HTML galleries.
Do **not** merge it into `main` until the original YODA normalization and
generator HT2-bias treatment have been validated.

## Inputs and output

The source is the **exported numerical plot data**, not generated `*.png`
files. On the AF, use the archived Rivet plotting directory whose layout is:

```
<source>/Zee/01_four_way_common_MC_shapes/MC_ZJETS/*__data.py
<source>/Zee/01_four_way_common_MC_shapes/MC_ZINC/*__data.py
<source>/Wenu/01_four_way_common_MC_shapes/MC_WJETS/*__data.py
<source>/Wenu/01_four_way_common_MC_shapes/MC_WINC/*__data.py
```

If starting with `AQP_Vjets_final_plots_20261118.tar.gz`, extract it in a
scratch directory (`tar -xzf ... -C <source>`) rather than committing it.

With Python, NumPy and Matplotlib available:

```bash
python3 validation/rivet/aqp_vjets_normalized_plot.py \
  --source /path/to/extracted/Vjets_final_plots \
  --output /data/aalida/AQP_Rivet_full/outputs/Vjets_corrected_shapes
python3 -m unittest discover -s validation/rivet -p 'test_vjets_normalized_plot.py' -v
```

The command creates a browsable `index.html`, PNG shape plots and
`shape_checks.csv` containing every normalization factor and a
total-variation distance to S111 where appropriate. Input exports are
parsed as AST literals, **not executed**.

## Physics and code constraints

- The **old nominal Wenu S111 v2** is invalid (wrong seed); use only the
  corrected Wenu S111 v1 from the final plotting archive.
- Original v2 plots used an artificial `CrossSection=1.0`; the newer
  samples used generator metadata. Their displayed absolute rates differ
  by large factors. The previous `PLOT:NormalizeToIntegral=1` invocation
  **did not actually yield unit-area numerical distributions**.
- Differential histograms are explicitly divided by their own
  bin-width-weighted integrals. Inclusive jet multiplicities are divided
  by their first bin. Derived charge asymmetries and jet ratios stay unscaled.
- Ratios omit numerically empty S111 bins and display only the 0.55–1.45
  interval; **the clipped tails must not be interpreted as agreement**.
- Expanded ATLAS/CMS, splitting-scale, and weight routine plots do **not**
  have four-configuration coverage. `MC_WKTSPLITTINGS` is missing.
  Two `ATLAS_2017_I1514251` plots had a MathText rendering error.
- Statistical uncertainties shown are approximate after area normalization:
  the correlation with the normalization denominator is not propagated.
- No statement on absolute cross sections, HT2 generation bias, FxFx
  matching physics, or agreement with experimental data follows from
  diagnostic PNGs alone.

The full 18 November plot archive, generated images and merged YODA
files remain on AF / in the conversation artifacts rather than in Git.
**Only reproducible source and documentation belong on this branch.**

**shortcut:** the input is the Rivet numerical plot export, not the
raw YODA bins. Upgrade to direct YODA recomputation when final
normalization, uncertainties and cross-section consistency are certified.
