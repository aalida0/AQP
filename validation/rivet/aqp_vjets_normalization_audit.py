#!/usr/bin/env python3
"""Audit normalization consistency in the original four-way Rivet exports.

Compare the integral of each ordinary differential histogram to the integral
of the S111 histogram for the same process and observable. Derived ratios,
asymmetries, and inclusive jet-multiplicity plots are not suitable for this
integral test and are excluded.

This tool is read-only for YODA/plot inputs; no physics scale factors are
computed or applied to histogram bins or uncertainties.
"""
import argparse
import csv
import math
from pathlib import Path

import numpy as np

from aqp_vjets_normalized_plot import (
    ANALYSES, CONFIGS, normalization_mode, read_export
)


def audit(source):
    rows = []
    for process, analyses in ANALYSES.items():
        for analysis in analyses:
            directory = source / process / "01_four_way_common_MC_shapes" / analysis
            for plot in sorted(directory.glob("*__data.py")):
                observable = plot.name.removesuffix("__data.py")
                if normalization_mode(observable) in (
                    "derived_ratio_unscaled", "inclusive_jet_bin"
                ):
                    continue
                edges, curves = read_export(plot)
                widths = np.diff(edges)
                integrals = {
                    config: float(np.nansum(y * widths))
                    for config, (y, _) in curves.items()
                }
                ref = integrals["S111"]
                for config in CONFIGS:
                    area = integrals[config]
                    ratio = area / ref if ref else float("nan")
                    if not math.isfinite(ratio) or ratio <= 0:
                        status = "UNDEFINED"
                    elif ratio < 0.5 or ratio > 2.0:
                        status = "OUTLIER"
                    else:
                        status = "IN_RANGE"
                    rows.append({
                        "process": process, "analysis": analysis,
                        "observable": observable, "config": config,
                        "integral": area, "relative_to_S111": ratio,
                        "status": status, "source": str(plot)
                    })
    if not rows:
        raise ValueError("No ordinary four-way differential histograms found")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--csv", type=Path, required=True)
    args = parser.parse_args()
    try:
        rows = audit(args.source)
    except (ValueError, FileNotFoundError, OSError) as exc:
        parser.error(str(exc))
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    for process in ANALYSES:
        for config in CONFIGS:
            relevant = [r["relative_to_S111"] for r in rows
                        if r["process"] == process and r["config"] == config
                        and r["status"] != "UNDEFINED"]
            if relevant:
                print(f"{process} {config}: n={len(relevant)} "
                      f"median_integral_ratio_to_S111={float(np.median(relevant)):.7g}")
    outliers = sum(r["status"] != "IN_RANGE" for r in rows
                   if r["config"] != "S111")
    print(f"INTEGRAL_AUDIT_ROWS={len(rows)} OUTLIER_ROWS={outliers} "
          f"CSV={args.csv}")
    print("NOTE: These are plot-export integrals, not independently "
          "validated physical cross sections.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
