#!/usr/bin/env python3
"""Reconstruct four-way AQP V+jets shapes from rivet-mkhtml numerical exports.

Diagnostic only: source __data.py files are parsed as AST literals, never executed.
This does NOT establish physical cross sections or correct generator HT2 bias.
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
        if not np.all(np.isfinite(y)) or not np.all(np.isfinite(err)):
            raise ValueError(f"{label}: nonfinite histogram")
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


def draw(edges, curves, mode, title, dest):
    fig, (ax, ratio) = plt.subplots(2, 1, figsize=(8.5, 6.4),
                                  sharex=True, gridspec_kw={"height_ratios": (3, 1)})
    centers = (edges[1:] + edges[:-1])/2
    if edges[0] > 0 and edges[-1]/edges[0] > 18:
        ax.set_xscale("log")
        ratio.set_xscale("log")
    ref = curves["S111"][0]
    reference_floor = max(float(np.max(np.abs(ref)))*2e-5, 1e-14)
    for label in CONFIGS:
        y, err = curves[label]
        (line,) = ax.plot(centers, y, lw=1.1, marker=".", markersize=2, label=label)
        if label == "S111":
            ax.fill_between(centers, y-err[0], y+err[1],
                            alpha=0.12, color=line.get_color())
        else:
            divided = np.divide(y, ref, out=np.full_like(y, np.nan),
                                where=np.abs(ref) > reference_floor)
            mask = np.isfinite(divided) & (np.abs(divided) < 5)
            ratio.plot(centers[mask], divided[mask], lw=1,
                       color=line.get_color(), label=label)
    ratio.axhline(1, lw=0.8, color="black", ls="--")
    ratio.set_ylim(0.55, 1.45)
    ratio.set_ylabel("/ S111")
    ratio.set_xlabel(title.split("/")[-1])
    ax.set_title(title)
    ax.set_ylabel({"unit_integral": "Unit-area density",
                   "inclusive_jet_bin": "Fraction relative to inclusive bin",
                   "derived_ratio_unscaled": "Unscaled dimensionless observable"}[mode])
    ax.legend(ncol=4, fontsize=9)
    ax.grid(alpha=0.2)
    ratio.grid(alpha=0.2)
    fig.text(0.02, 0.01, "Diagnostic from Rivet plot exports; not YODA-level validation.",
             fontsize=8)
    fig.tight_layout(rect=(0, 0.025, 1, 1))
    dest.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(dest, dpi=130)
    plt.close(fig)


def run(source, output):
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
                    draw(edges, curves, mode, f"{proc}/{analysis}/{name}", target)
                    figures.append((name, target.relative_to(output).as_posix()))
                    baseline = curves["S111"][0]
                    for cfg in CONFIGS:
                        tv = (0.5*float(np.dot(np.abs(curves[cfg][0]-baseline),
                                             np.diff(edges))) if mode=="unit_integral"
                              else "")
                        records.append((proc,analysis,name,cfg,mode,factors[cfg],tv))
                except (ValueError, KeyError, OSError, AssertionError) as exc:
                    errors.append(f"{file}: {exc}")
            galleries.append((proc, analysis, figures))
    output.mkdir(parents=True, exist_ok=True)
    with (output/"shape_checks.csv").open("w", newline="") as fp:
        w = csv.writer(fp)
        w.writerow(("process","analysis","histogram","configuration",
                    "normalization","original_scale","TV_against_S111"))
        w.writerows(records)
    parts = ['<!doctype html><meta charset="utf-8"><title>AQP V+jets shape audit</title>',
             '<h1>AQP V+jets — four-way shape diagnostic</h1>',
             '<p>Reconstructed from rivet-mkhtml exports, not original YODA. '
             'Absolute rates and HT2 bias are NOT validated.</p>',
             '<p><a href="shape_checks.csv">Normalization and shape checks (CSV)</a></p>']
    for proc, analysis, figures in galleries:
        parts.append(f"<h2>{html.escape(proc)} / {html.escape(analysis)} "
                     f"({len(figures)} figures)</h2>")
        for name, path in figures:
            parts.append(f'<details><summary>{html.escape(name)}</summary>'
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
    args = parser.parse_args()
    raise SystemExit(run(args.source, args.output))


if __name__ == "__main__":
    main()
