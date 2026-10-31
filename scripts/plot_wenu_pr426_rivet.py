#!/usr/bin/env python3
"""Plot signed-weight before/after PR426 jet-DeltaR shapes from YODA.
Usage: python3 scripts/plot_wenu_pr426_rivet.py BEFORE.yoda.gz AFTER.yoda.gz OUTDIR
Produces four plots and prints signed fraction in 0.4 <= dR < 1.
The error bands omit correlations due to shape normalization and common seeds.
"""
import argparse
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import yoda


def get_hist(data, hist_name):
    matches = [(k, obj) for k, obj in data.items()
               if k.endswith("/" + hist_name) and "RAW" not in k]
    if len(matches) != 1:
        raise RuntimeError("Expected one %s, found %r" %
                           (hist_name, [k for k, _ in matches]))
    return matches[0][1]


def arrays(hist):
    bins = hist.bins()
    x = np.array([.5 * (b.xMin() + b.xMax()) for b in bins])
    dx = np.array([b.xMax() - b.xMin() for b in bins])
    w = np.array([b.sumW() for b in bins])
    w2 = np.array([b.sumW2() for b in bins])
    return x, dx, w, w2


def unit_shape(hist):
    x, dx, w, w2 = arrays(hist)
    total = w.sum()
    if abs(total) < 1.e-20:
        raise RuntimeError("Signed integral too small; cannot normalize.")
    return x, w / (total*dx), np.sqrt(w2) / (abs(total)*dx)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("outdir", type=Path)
    args = parser.parse_args()
    before, after = yoda.read(str(args.before)), yoda.read(str(args.after))
    args.outdir.mkdir(parents=True, exist_ok=True)

    for name in ("drjj", "drjj_ptw_lt100", "drjj_ptw_100_200", "drjj_ptw_ge200"):
        hb, ha = get_hist(before, name), get_hist(after, name)
        x, b, be = unit_shape(hb)
        xa, a, ae = unit_shape(ha)
        if not np.array_equal(x, xa):
            raise RuntimeError("Binning mismatch in " + name)
        ratio = np.divide(a, b, out=np.full_like(b, np.nan), where=b != 0.)
        # Diagnostic independent-bin errors, NOT a covariance-aware test.
        rerr = np.abs(ratio) * np.sqrt(
            np.divide(ae, a, out=np.zeros_like(ae), where=a != 0.)**2
            + np.divide(be, b, out=np.zeros_like(be), where=b != 0.)**2)
        fig, (ax, bot) = plt.subplots(2, 1, sharex=True,
                            gridspec_kw={"height_ratios": [3, 1]}, figsize=(7, 6))
        ax.errorbar(x, b, yerr=be, fmt=".", label="Before PR426")
        ax.errorbar(x, a, yerr=ae, fmt=".", label="After PR426")
        ax.axvspan(.4, 1., alpha=.1, label="Target: 0.4 < dR < 1")
        ax.set_ylabel("Unit-area signed dN/dDeltaR")
        ax.legend()
        bot.errorbar(x, ratio, yerr=rerr, fmt=".")
        bot.axhline(1., linestyle="--", linewidth=1.)
        bot.set(xlabel="DeltaR(j1,j2)", ylabel="After / Before")
        fig.suptitle(name + ": nominal signed-weight diagnostic")
        fig.tight_layout()
        output = args.outdir / (name + ".png")
        fig.savefig(output, dpi=180)
        plt.close(fig)
        print("PLOT", output)

        _, _, wb, _ = arrays(hb)
        _, _, wa, _ = arrays(ha)
        window = (x >= .4) & (x < 1.)
        fb, fa = wb[window].sum()/wb.sum(), wa[window].sum()/wa.sum()
        print("SMALL_DR_SIGNED_FRACTION", name,
              "before=%.6g" % fb, "after=%.6g" % fa,
              "change_percentage_points=%.4g" % (100*(fa-fb)))


if __name__ == "__main__":
    main()
