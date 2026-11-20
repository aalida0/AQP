#!/usr/bin/env python3
"""Plot existing four-way AQP V+jets Rivet exports using mplhep ATLAS style.

This is a shape-only diagnostic from Rivet numerical plot exports.
The original YODA files, Rivet analyses, experimental references, and absolute
cross-section/HT2-bias normalization are not modified or validated.
"""
import argparse
import ast
import csv
import html
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

CONFIGS = ("S111", "D111", "D221", "D441")
PLOT_LABELS = {
    "S111": "MC@NLO, 111",
    "D111": "MC@NLO-Δ, 111",
    "D221": "MC@NLO-Δ, 221",
    "D441": "MC@NLO-Δ, 441",
}
ANALYSES = {"Zee": ("MC_ZJETS", "MC_ZINC"),
            "Wenu": ("MC_WJETS", "MC_WINC")}


def literal(node):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.Tuple, ast.List)):
        return [literal(x) for x in node.elts]
    if isinstance(node, ast.Dict):
        return {literal(k): literal(v) for k, v in zip(node.keys, node.values)}
    if isinstance(node, ast.Name) and node.id in ("nan", "inf"):
        return float(node.id)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -literal(node.operand)
    raise ValueError("non-literal input in plot data: " + ast.dump(node)[:120])


def read_export(path):
    fields = {}
    for node in ast.parse(path.read_text()).body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        name = node.targets[0]
        if isinstance(name, ast.Name) and name.id in ("xedges", "yvals", "yerrs"):
            fields[name.id] = literal(node.value)
    if set(fields) != {"xedges", "yvals", "yerrs"}:
        raise ValueError(f"missing plot data fields: {path}")
    keys = {}
    for key in fields["yvals"]:
        found = [label for label in CONFIGS if label in key.split("_")]
        if len(found) != 1 or found[0] in keys:
            raise ValueError(f"ambiguous configuration key: {key}")
        keys[found[0]] = key
    if set(keys) != set(CONFIGS):
        raise ValueError(f"not all four configurations present: {path}")
    edges = np.asarray(fields["xedges"][keys["S111"]], dtype=float)
    if len(edges) < 2 or not np.all(np.isfinite(edges)) or np.any(np.diff(edges) <= 0):
        raise ValueError("invalid bin edges")
    curves = {}
    for label, key in keys.items():
        other = np.asarray(fields["xedges"][key], dtype=float)
        if other.shape != edges.shape or not np.allclose(other, edges, rtol=1e-5, atol=1e-8):
            raise ValueError(f"{label}: inconsistent bin edges")
        y = np.asarray(fields["yvals"][key], dtype=float)
        err = np.asarray(fields["yerrs"][key], dtype=float)
        if y.shape != (len(edges)-1,) or err.shape != (2, len(y)):
            raise ValueError(f"{label}: incompatible y/error shapes")
        valid = np.isfinite(y) & np.all(np.isfinite(err), axis=0)
        if not np.all(valid):
            # Derived ratios may have undefined tails (zero denominator).
            # Hide them as gaps; never invent zero content or zero uncertainty.
            if normalization_mode(path.name.removesuffix("__data.py")) != "derived_ratio_unscaled":
                raise ValueError(f"{label}: nonfinite histogram in a physical distribution")
            if not np.any(valid):
                raise ValueError(f"{label}: no defined bins in derived observable")
            y = np.where(valid, y, np.nan)
            err = np.where(valid[None, :], err, np.nan)
        curves[label] = (y, err)
    return edges, curves


def normalization_mode(name):
    if ("pmratio" in name or "chargeasymm" in name
            or name == "jet_multi_ratio"):
        return "derived_ratio_unscaled"
    if name == "jet_multi_inclusive":
        return "inclusive_jet_bin"
    return "unit_integral"


def normalize(edges, curves, mode):
    result, factors = {}, {}
    for label, (y, err) in curves.items():
        if mode == "unit_integral":
            scale = float(np.dot(y, np.diff(edges)))
        elif mode == "inclusive_jet_bin":
            scale = float(y[0])
        else:
            scale = 1.0
        if not math.isfinite(scale) or scale <= 0:
            raise ValueError(f"{label}: nonpositive normalization {scale}")
        result[label] = (y/scale, err/scale)
        factors[label] = scale
        if mode == "unit_integral":
            assert abs(np.dot(result[label][0], np.diff(edges))-1) < 1e-9
    return result, factors


def plot_metadata(path):
    """Recover plot labels/scales from rivet-mkhtml code without executing it."""
    fields = {"ax_xLabel": path.stem, "ax_title": path.stem,
              "ax_xScale": "linear", "ax_yScale": "linear"}
    if not path.is_file():
        return fields
    for node in ast.parse(path.read_text()).body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id in fields
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)):
            fields[node.targets[0].id] = node.value.value
    return fields


def ratio_values(curves, mode):
    """Never divide derived observables by an asymmetry that may vanish."""
    reference = curves["S111"][0]
    if mode == "derived_ratio_unscaled":
        return {key: curves[key][0] - reference for key in CONFIGS[1:]}, 0.0
    floor = max(1e-14, float(np.nanmax(np.abs(reference))) * 2e-5)
    ratios = {}
    for key in CONFIGS[1:]:
        y = curves[key][0]
        valid = (np.isfinite(y) & np.isfinite(reference)
                 & (np.abs(reference) > floor) & (np.abs(y) > floor))
        ratios[key] = np.divide(y, reference, out=np.full_like(y, np.nan),
                                where=valid)
    return ratios, 1.0


def draw(edges, curves, mode, title, dest, source_plot):
    """Produce stepped ATLAS-style histograms and a lower comparison panel."""
    import mplhep as hep

    meta = plot_metadata(source_plot)
    with plt.style.context(hep.style.ATLAS), plt.rc_context({
        "font.size": 12, "axes.labelsize": 13, "axes.titlesize": 13,
        "xtick.labelsize": 10, "ytick.labelsize": 10,
        "legend.fontsize": 10, "lines.linewidth": 1.5,
    }):
        fig, (ax, rax) = plt.subplots(
            2, 1, sharex=True, figsize=(8.6, 6.9),
            gridspec_kw={"height_ratios": (3.3, 1), "hspace": 0.08},
        )
        colors = plt.rcParams["axes.prop_cycle"].by_key()["color"][:4]
        for key, color in zip(CONFIGS, colors):
            y, err = curves[key]
            hep.histplot(y, bins=edges, ax=ax, histtype="step",
                         label=PLOT_LABELS[key], color=color, linewidth=1.5)
            if key == "S111":
                # Errors are only approximate after per-histogram area normalization.
                ax.fill_between(edges,
                                np.r_[y - err[0], y[-1] - err[0, -1]],
                                np.r_[y + err[1], y[-1] + err[1, -1]],
                                step="post", alpha=0.15, color=color)
        ratios, baseline = ratio_values(curves, mode)
        for key, color in zip(CONFIGS[1:], colors[1:]):
            hep.histplot(ratios[key], bins=edges, ax=rax,
                         histtype="step", color=color, linewidth=1.4)
        rax.axhline(baseline, ls="--", color="black", linewidth=0.9)
        if mode == "derived_ratio_unscaled":
            ax.set_ylabel("Derived observable")
            rax.set_ylabel("Difference to nominal")
        elif mode == "inclusive_jet_bin":
            ax.set_ylabel("Relative to first bin")
            rax.set_ylabel("Ratio to nominal")
        else:
            ax.set_ylabel("Unit-area density")
            rax.set_ylabel("Ratio to nominal")
        if meta["ax_xScale"] == "log" and edges[0] > 0:
            rax.set_xscale("log")
        if (meta["ax_yScale"] == "log"
                and all(np.nanmin(curves[k][0]) >= 0 for k in CONFIGS)
                and any(np.nanmax(curves[k][0]) > 0 for k in CONFIGS)):
            ax.set_yscale("log")
        rax.set_xlabel(meta["ax_xLabel"])
        ax.set_title(meta["ax_title"], loc="right", fontsize=12)
        hep.atlas.label("Internal", data=False, com=13, ax=ax)
        ax.text(0.02, 0.73, " · ".join(title.split("/")[:2]),
                transform=ax.transAxes, fontsize=10)
        ax.legend(loc="lower right", bbox_to_anchor=(1, 1.065),
                  ncol=2, fontsize=9, frameon=False)
        fig.text(0.04, 0.012,
                 "Shape-only diagnostic from Rivet exports; rates and HT2 bias "
                 "not validated. Uncertainty band neglects normalization covariance.",
                 fontsize=8)
        fig.subplots_adjust(left=0.14, right=0.98, top=0.80, bottom=0.15)
        dest.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(dest, dpi=155)
        fig.savefig(dest.with_suffix(".pdf"))
        plt.close(fig)


def run(source, output, check_only=False):
    records = []
    galleries = []
    errors = []
    for proc, analyses in ANALYSES.items():
        for analysis in analyses:
            folder = source/proc/"01_four_way_common_MC_shapes"/analysis
            files = sorted(folder.glob("*__data.py"))
            if not files:
                errors.append(f"missing exports: {folder}")
            figures = []
            for file in files:
                name = file.name.removesuffix("__data.py")
                try:
                    edges, raw = read_export(file)
                    mode = normalization_mode(name)
                    curves, factors = normalize(edges, raw, mode)
                    target = output/proc/analysis/(name+".png")
                    if not check_only:
                        draw(edges, curves, mode, f"{proc}/{analysis}/{name}",
                             target, file.with_name(name + ".py"))
                    figures.append((name, target.relative_to(output).as_posix()))
                    ratios, _ = ratio_values(curves, mode)
                    baseline = curves["S111"][0]
                    for cfg in CONFIGS:
                        tv = (0.5*float(np.dot(np.abs(curves[cfg][0]-baseline),
                                             np.diff(edges))) if mode=="unit_integral"
                              else "")
                        masked = int(np.count_nonzero(~np.isfinite(raw[cfg][0])))
                        records.append((proc,analysis,name,cfg,mode,factors[cfg],tv,masked))
                except (ValueError, KeyError, OSError, AssertionError) as exc:
                    errors.append(f"{file}: {exc}")
            galleries.append((proc, analysis, figures))
    output.mkdir(parents=True, exist_ok=True)
    with (output/"shape_checks.csv").open("w", newline="") as fp:
        w = csv.writer(fp)
        w.writerow(("process","analysis","histogram","configuration",
                    "normalization","original_scale","TV_against_S111","undefined_bins"))
        w.writerows(records)
    parts = ['<!doctype html><meta charset="utf-8"><title>AQP V+jets shape audit</title>',
             '<h1>AQP V+jets — four-way shape diagnostic</h1>',
             '<p>ATLAS-style mplhep histograms reconstructed from Rivet plot exports, not original YODA. '
             'Absolute rates and HT2 bias are NOT validated.</p>',
             '<p><a href="shape_checks.csv">Normalization and shape checks (CSV)</a></p>']
    for proc, analysis, figures in galleries:
        parts.append(f"<h2>{html.escape(proc)} / {html.escape(analysis)} "
                     f"({len(figures)} figures)</h2>")
        for name, path in figures:
            parts.append(f'<details><summary>{html.escape(name)}</summary>'
                         f'<a href="{html.escape(path).removesuffix(".png")}.pdf">PDF</a><br>'
                         f'<img style="max-width:100%" loading="lazy" src="{html.escape(path)}">'
                         '</details>')
    if errors:
        parts.append("<h2>Errors</h2><pre>"+html.escape("\n".join(errors))+"</pre>")
    (output/"index.html").write_text("\n".join(parts))
    print(f"PLOTS={sum(len(x[2]) for x in galleries)} ERROR_COUNT={len(errors)} OUTPUT={output}")
    for error in errors: print("ERROR:", error)
    return int(bool(errors))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path,
                        help="Directory containing Zee/ and Wenu/ plot exports")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--check-only", action="store_true",
                        help="validate export data without needing mplhep")
    args = parser.parse_args()
    raise SystemExit(run(args.source, args.output, args.check_only))


if __name__ == "__main__":
    main()
