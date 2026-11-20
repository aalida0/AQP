# V+jets — existing four-way histograms with mplhep ATLAS style

This stage intentionally plots **only the existing 101 common-MC histograms**.
Incomplete ATLAS/CMS/MC_WEIGHTS and additional splitting-scale analyses remain
for a later production stage. The original Rivet analyses and
`rivet-mkhtml` output are not modified.

## Plots

`aqp_vjets_mplhep_plot.py` generates PNG and PDF stepped histograms,
a lower comparison panel, an HTML gallery, and a normalization CSV.

- Inputs: existing numerical `*__data.py` exports produced by Rivet's
  plotting tools; they are parsed as AST literals, **never executed**.
- Original x-axis label, title and log-scale preferences are read safely
  from the adjacent auto-generated Rivet plot script, when available.
- S111 → **MC@NLO, 111**; D111/D221/D441 →
  **MC@NLO-Δ, 111/221/441**.
- Differential distributions are divided by their own bin-width-weighted
  integrals. Inclusive jet multiplicities are scaled to the first bin.
  Derived asymmetries/ratios remain in their original units.
- The lower panel shows configuration/S111 for ordinary histograms,
  or **configuration − S111** for derived ratios/asymmetries, where a ratio
  to a zero-crossing asymmetry would be nonsensical.
- Undefined/empty bins are masked, not replaced by zeros. Ratio-axis limits
  are not artificially clipped.
- The S111 uncertainty band is based on Rivet-export bin uncertainties
  divided by the same integral; the covariance introduced by normalization
  is **not available**, so it is approximate.

## AF setup and execution

Make an **independent plotting environment** (no `asetup` required):

```bash
python3 -m venv ~/.venvs/aqp-mplhep
~/.venvs/aqp-mplhep/bin/python -m pip install --upgrade pip
~/.venvs/aqp-mplhep/bin/python -m pip install numpy matplotlib mplhep
```

Then from `~/AQP`:

```bash
~/.venvs/aqp-mplhep/bin/python validation/rivet/aqp_vjets_mplhep_plot.py \
  --source /data/aalida/AQP_Rivet_full/outputs/Vjets_final_plots_20261118 \
  --output /data/aalida/AQP_Rivet_full/outputs/Vjets_mplhep_20261120 \
  --check-only
```

Expected: `PLOTS=101 ERROR_COUNT=0`. For the full rendering pass,
remove `--check-only` or submit the included single Condor worker
`aqp_vjets_mplhep.sub`. This job needs **no Rivet/YODA Python modules**.

```bash
cd ~/AQP/validation/rivet
mkdir -p condor_logs
condor_submit aqp_vjets_mplhep.sub
```

Outputs:

```
/data/aalida/AQP_Rivet_full/outputs/Vjets_mplhep_20261120/index.html
/data/aalida/AQP_Rivet_full/outputs/Vjets_mplhep_20261120/manifest.csv
```

## Scope and limitations

This is **shape-only**. Mixed old/new Rivet normalization and the HT2 bias
are not certified for physical rates. No experiment-data comparisons or
complete four-config ATLAS/CMS routines are implied. The correctly reseeded
Wenu S111 source must be used (already selected in the final archive).
The source is exported plot data, not original YODA, so bin-error covariance
cannot be recovered. The plotting code's `mplhep` runtime check must be
performed on AF; it is not included in the local dependency-free validation.

Do not merge to `main` until the physics/normalization validation is done.
