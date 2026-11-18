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
- Four derived observables have undefined tail bins in the Rivet exports:
  `Zee/MC_ZJETS/jet_multi_ratio` (1 bin),
  `Wenu/MC_WJETS/jet_multi_ratio` (1 bin),
  `Wenu/MC_WINC/W_chargeasymm_eta` (2 bins), and
  `Wenu/MC_WINC/W_chargeasymm_pT` (4 bins).
  The parser masks both y-values and uncertainties in these bins and leaves
  gaps in curves and ratios; it does **not** silently substitute zeros.
  `shape_checks.csv` records a per-configuration `undefined_bins` count.
- **Charge content verified from the production JOs:** despite the `Wenu`
  label, all four W+jets JobOptions define `e = e+ e-`, `nu = ve ve~`
  and generate `p p > e nu` with 0, 1 and 2 jets. This includes
  `W+ -> e+ ve` **and** `W- -> e- ve~`. The corrected-seed S111 JO
  retains this same process definition. Both charge-specific `Wplus_pT`
  and `Wminus_pT` histograms are populated.
- `MC_WINC/W_chargeasymm_eta` means **lepton-charge asymmetry**
  `(d sigma(l+) - d sigma(l-))/(d sigma(l+) + d sigma(l-))` versus lepton eta.
  Despite its histogram name, `MC_WINC/W_chargeasymm_pT` is the **ratio**
  `d sigma(W+)/d sigma(W-)` versus W pT, not a difference-over-sum.
  Both require both W charges (verified above) and careful signed-weight
  uncertainty treatment. In the uploaded corrected gallery the latter's
  high-pT tail shows large excursions and even a negative D441 bin:
  **do not interpret those statistically unstable signed-weight tails as
  physical negative production rates**.
  Do not mistake `Wenu` for positive-charge-only production.
- The corrected-shape archive holds **101 PNG plots only**:
  `MC_ZJETS` (40), `MC_ZINC` (7), `MC_WJETS` (40), and
  `MC_WINC` (14). These are reconstructed four-configuration MC
  comparisons, **not** all expanded ATLAS/CMS/jet-splitting/weight
  plots, and not comparisons against experimental data.
- In these figures, top panels show individually unit-area normalized
  differential distributions, except inclusive jet multiplicities
  (scaled to the inclusive first bin) and derived asymmetries/ratios
  (left in their original dimensionless units); lower panels are the
  configuration's bin-by-bin value divided by S111. This is useful for
  comparing shapes, **not** for cross-section, acceptance or
  absolute W+/W− production-rate conclusions.
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
