#!/usr/bin/env python3
"""AQP PR426 Wenu before/after: stable signed-weight shape diagnostics.

Use Rivet 4/YODA 2 /RAW/ histograms, which expose sumW and sumW2.
Rebin 0.05-width native bins to physics-driven coarse bins, normalize the
DISPLAYED 0.4 <= DeltaR < 3 region, and plot the DIFFERENCE, not a
numerically unstable After/Before ratio.

Statistical caveats:
  - within-sample uncertainty uses a delta-method approximation for
    self-normalized signed weights and mutually exclusive histogram bins;
  - before/after difference uncertainty assumes independent samples;
    the samples might share random seeds and have unknown covariance;
  - this is a diagnostic, NOT a rigorous correlated hypothesis test.

Does not change the original YODA files.
"""

import argparse
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import yoda

# Preserve 0.2-bin resolution in the 0.4--1.0 target region.
# Elsewhere use larger bins to limit signed-weight cancellations.
EDGES = np.array([0.4, 0.6, 0.8, 1.0, 1.4, 1.8, 2.2, 2.6, 3.0])
OBS = (
    ("drjj", "Inclusive (at least two jets)"),
    ("drjj_ptw_lt100", r"$p_T(e+\nu_e)$ proxy $<100$ GeV"),
    ("drjj_ptw_100_200", r"$100 \leq p_T(e+\nu_e)$ proxy $<200$ GeV"),
    ("drjj_ptw_ge200", r"$p_T(e+\nu_e)$ proxy $\geq200$ GeV"),
)


def get_raw(data, name):
    selected = [(key, value) for key, value in data.items()
                if "/RAW/" in key and key.endswith("/" + name)]
    if len(selected) != 1:
        raise ValueError(f"Expected one RAW histogram for {name}: "
                         f"found {[key for key, _ in selected]}")
    return selected[0][1]


def rebinned(hist, edges=EDGES):
    w = np.zeros(len(edges)-1)
    v = np.zeros(len(edges)-1)
    covered = np.zeros(len(edges)-1)
    original_bins = hist.bins()
    for b in original_bins:
        low, high = float(b.xMin()), float(b.xMax())
        if high <= edges[0] + 1e-10 or low >= edges[-1] - 1e-10:
            continue
        idx = int(np.searchsorted(edges, (low + high)/2, side="right") - 1)
        if idx < 0 or idx >= len(w) or low < edges[idx]-1e-8 or high > edges[idx+1]+1e-8:
            raise ValueError(f"Original bin [{low}, {high}] crosses a coarse bin edge")
        w[idx] += float(b.sumW())
        v[idx] += float(b.sumW2())
        covered[idx] += high - low
    if not np.allclose(covered, np.diff(edges), rtol=0, atol=1e-7):
        raise ValueError(f"Incomplete original-bin coverage: {covered}")
    if np.any(v < -1e-10):
        raise ValueError("Negative sumW2 is impossible; inspect YODA input")
    return w, np.maximum(v, 0.0)


def fraction_and_error(w, v, indices):
    """Ratio of signed weight sums, with variance of a self-normalized ratio.

    We assume mutually exclusive fills (one entry in this histogram per event),
    and independent events within a sample. The denominator is the sum over
    the DISPLAYED region, not the total cross section.
    """
    total, vtotal = float(w.sum()), float(v.sum())
    if vtotal == 0 or not np.isfinite(total) or abs(total) < 1e-12 * np.sqrt(vtotal):
        raise ValueError("Signed normalization vanishes or is numerically unstable")
    wi, vi = float(w[indices].sum()), float(v[indices].sum())
    frac = wi / total
    var = ((1-frac)**2 * vi + frac**2 * max(vtotal-vi, 0.0))/total**2
    return frac, np.sqrt(max(var, 0.0))


def shape_and_error(w, v, edges=EDGES):
    widths = np.diff(edges)
    fractions = []
    fraction_errors = []
    for i in range(len(w)):
        mask = np.zeros(len(w), dtype=bool)
        mask[i] = True
        frac, err = fraction_and_error(w, v, mask)
        fractions.append(frac)
        fraction_errors.append(err)
    return np.asarray(fractions)/widths, np.asarray(fraction_errors)/widths


def report(name, b, bv, a, av):
    # The first three bins are exactly 0.4 <= DeltaR < 1.0.
    mask = (EDGES[:-1] >= 0.4 - 1e-9) & (EDGES[1:] <= 1.0 + 1e-9)
    fb, sb = fraction_and_error(b, bv, mask)
    fa, sa = fraction_and_error(a, av, mask)
    d = fa-fb
    # For reference only: no inter-sample correlation available here.
    sd = np.hypot(sa, sb)
    def neff(w, v):
        return (w.sum()**2/v.sum()) if v.sum() > 0 else 0.0
    print(f"OBS={name}")
    print(f"  displayed_range=[0.4,3.0)  "
          f"before_sumW={b.sum():.8g}  after_sumW={a.sum():.8g}")
    print(f"  before_Neff={neff(b,bv):.2f}  after_Neff={neff(a,av):.2f} "
          "(signed, displayed-range)")
    print(f"  target_0p4_1p0_before={fb:.6g} +/- {sb:.3g}")
    print(f"  target_0p4_1p0_after ={fa:.6g} +/- {sa:.3g}")
    print(f"  target_difference_after_minus_before={d:.6g} +/- {sd:.3g} "
          "(naive, assumes independent samples)")
    if min(neff(b,bv), neff(a,av)) < 30:
        print("  WARNING: very low effective entries; shape is unstable")


def make_plot(name, title, b, bv, a, av, output):
    xb, eb = shape_and_error(b, bv)
    xa, ea = shape_and_error(a, av)
    centers = (EDGES[:-1] + EDGES[1:]) / 2
    delta = xa - xb
    # Naive error: inter-sample covariance NOT included; for display only.
    e_delta = np.hypot(ea, eb)

    fig, (top, bottom) = plt.subplots(
        2, 1, figsize=(9.3, 7.2), sharex=True,
        gridspec_kw={"height_ratios": [2.6, 1.2], "hspace": 0.07},
    )
    top.axvspan(0.4, 1.0, color="#DCECF1", alpha=0.75,
                label=r"Target $0.4\leq\Delta R<1.0$")
    bottom.axvspan(0.4, 1.0, color="#DCECF1", alpha=0.75)
    top.errorbar(centers - 0.014, xb, yerr=eb, fmt="o", ms=5,
                 capsize=2.5, lw=1.2, color="#1f77b4", label="Before PR426")
    top.errorbar(centers + 0.014, xa, yerr=ea, fmt="s", ms=4.5,
                 capsize=2.5, lw=1.2, color="#e26c16", label="After PR426")
    top.set_ylabel(r"$(1/\sum w)\,d(\sum w)/d\Delta R$")
    top.set_title(f"PR426: $\\Delta R(j_1,j_2)$ — {title}")
    top.legend(loc="best", frameon=False, fontsize=9)
    top.grid(axis="y", alpha=0.18)
    top.set_xlim(0.4, 3.0)

    bottom.errorbar(centers, delta, yerr=e_delta, fmt="o", ms=4,
                    lw=1.1, capsize=2, color="black")
    bottom.axhline(0.0, lw=1, color="gray", linestyle="--")
    bottom.set_ylabel("After − Before\n(density difference)")
    bottom.set_xlabel(r"$\Delta R(j_1,j_2)$")
    bottom.set_xticks(EDGES)
    bottom.grid(axis="y", alpha=0.18)
    fig.text(0.5, 0.005,
             "Coarse rebinning of RAW signed weights. Normalized within 0.4 ≤ ΔR < 3.0. "
             "Error on difference ignores before/after covariance.",
             ha="center", va="bottom", fontsize=8, color="#555555")
    fig.subplots_adjust(left=0.14, right=0.985, top=0.92, bottom=0.12)
    fig.savefig(output, dpi=180)
    plt.close(fig)
    print(f"PLOT={output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("outdir", type=Path)
    args = parser.parse_args()
    if args.before.resolve() == args.after.resolve():
        parser.error("Before and after must be distinct files")
    data_b = yoda.read(str(args.before))
    data_a = yoda.read(str(args.after))
    # Validate all input histograms before producing any partial figures.
    inputs = [(name, title, rebinned(get_raw(data_b, name)),
               rebinned(get_raw(data_a, name))) for name, title in OBS]
    args.outdir.mkdir(parents=True, exist_ok=True)
    print("CAVEAT: all difference errors ignore possible before/after covariance.")
    for name, title, (b, bv), (a, av) in inputs:
        report(name, b, bv, a, av)
        make_plot(name, title, b, bv, a, av, args.outdir / f"{name}_coarse.png")


if __name__ == "__main__":
    main()
