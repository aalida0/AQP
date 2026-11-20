#!/usr/bin/env python3
"""Presentation-only V+jets shape comparison via original Rivet plot scripts.

Original Rivet binning, errorbar code, colors and legend labels are used.
Only the per-histogram normalization is changed for shape presentation.
Ratio-panel values and statistical errors scale with the corresponding curves.
No original YODA/source/plot-export file is edited; rates MUST NOT be inferred.
"""
import argparse
import csv
import html
import math
from pathlib import Path

import numpy as np

from aqp_vjets_mplhep_plot import ANALYSES, inspect_script, restyle_script
from aqp_vjets_normalized_plot import normalization_mode


def rescale_plot_data(data, observable):
    """In-memory presentation shapes; preserve Rivet errors up to scaling.

    Unit area for differential distributions; first bin for inclusive jet
    multiplicities. Derived asymmetries and ratios are left untouched.
    The bin-error covariance induced by normalization is unavailable.
    """
    mode = normalization_mode(observable)
    if mode == "derived_ratio_unscaled":
        return {"mode": mode, "scales": {label: 1.0 for label in data["yvals"]}}
    keys = list(data["yvals"])
    reference = next((key for key in keys if "_S111_" in key), None)
    if not reference or len(keys) != 4:
        raise ValueError("Expected four curves including S111: " + observable)

    scales = {}
    refedges = np.asarray(data["xedges"][reference], dtype=float)
    for label in keys:
        y = np.asarray(data["yvals"][label], dtype=float)
        edges = np.asarray(data["xedges"][label], dtype=float)
        if (len(y) != len(edges) - 1 or edges.shape != refedges.shape
                or not np.allclose(edges, refedges, rtol=1e-6, atol=1e-9)):
            raise ValueError("Incompatible Rivet bin edges: " + label)
        if not np.all(np.isfinite(y)):
            raise ValueError("Nonfinite ordinary histogram: " + label)

        if mode == "inclusive_jet_bin":
            scale = float(y[0])
        else:
            scale = float(np.dot(y, np.diff(edges)))

        if not math.isfinite(scale) or scale <= 0:
            raise ValueError("Invalid integral or reference bin: " + label)
        scales[label] = scale

    for label in keys:
        scale = scales[label]
        data["yvals"][label] = np.asarray(data["yvals"][label], float) / scale
        data["yerrs"][label] = np.asarray(data["yerrs"][label], float) / scale

        ratio_factor = scales[reference] / scale
        data["ratio0_yvals"][label] = (np.asarray(data["ratio0_yvals"][label], float)
                                       * ratio_factor)
        data["ratio0_yerrs"][label] = (np.asarray(data["ratio0_yerrs"][label], float)
                                       * ratio_factor)

    for field, ratio in (("variation_yvals", False),
                         ("ratio0_variation_vals", True)):
        for key, values in data.get(field, {}).items():
            owner = next((lab for lab in keys if key.startswith(lab)), None)
            if owner:
                factor = scales[reference] / scales[owner] if ratio else 1.0 / scales[owner]
                data[field][key] = np.asarray(values, float) * factor
    return {"mode": mode, "scales": scales}


def present_source(script, mode):
    """Modify an in-memory copy of the Rivet plot, never the source file."""
    original = script.read_text(encoding="utf-8")
    code = restyle_script(original)

    # Keep the legend in the original Rivet position and move the ATLAS label
    # into an unobstructed upper-right corner of the main panel.
    needle = "hep.atlas.label('Internal', data=False, ax=ax, loc=1, fontsize=11)"
    mark = ("ax.text(0.975, 0.96, r'$\\bf{ATLAS}$ Simulation Internal', "
            "ha='right', va='top', transform=ax.transAxes, fontsize=11)")
    if needle in code:
        code = code.replace(needle, mark, 1)

    if mode == "derived_ratio_unscaled":
        return code
    anchor = f"exec(open(prefix+'{script.stem}__data.py').read(), dataf)"
    if code.count(anchor) != 1:
        raise ValueError("Rivet data import anchor missing: " + script.name)
    code = code.replace(
        anchor, anchor + f"\n_aqp_scale = rescale_plot_data(dataf, {script.stem!r})", 1)

    # A pb-based label would be incorrect after shape normalization.
    label = "Unit-area normalized shape"
    if mode == "inclusive_jet_bin":
        label = "Yield relative to first jet bin"
    elif "/GeV" in inspect_script(original).get("ax_yLabel", ""):
        label = "Unit-area density [GeV$^{-1}$]"
    import re
    code, n = re.subn(r"(?m)^ax_yLabel\s*=.*$", f"ax_yLabel = {label!r}", code)
    if n != 1:
        raise ValueError("Rivet y-axis label anchor missing: " + script.name)

    # Original absolute-rate y limits are not applicable to normalized shapes.
    anchor = "ax.set_ylim(yLims)"
    if code.count(anchor) != 1:
        raise ValueError("Rivet absolute-rate y limit anchor missing")
    code = code.replace(
        anchor, anchor + "\nax.set_autoscaley_on(True)"
                         "\nax.relim()"
                         "\nax.autoscale_view(scalex=False, scaley=True)", 1)
    # Original ratio panel limits remain as defined in the Rivet plot.
    return code


def render_one(script, destination, check_only=False):
    mode = normalization_mode(script.stem)
    code = present_source(script, mode)
    compile(code, str(script), "exec")

    export = script.with_name(script.stem + "__data.py")
    data = {}
    exec(compile(export.read_text(encoding="utf-8"), str(export), "exec"), data)
    stats = rescale_plot_data(data, script.stem)

    if not check_only:
        destination.mkdir(parents=True, exist_ok=True)
        env = {"__name__": "__main__", "__file__": str(script.resolve()),
               "YODA_USER_PLOT_PATH": str(destination.resolve()),
               "rescale_plot_data": rescale_plot_data}
        exec(compile(code, str(script), "exec"), env)
        for suffix in (".png", ".pdf"):
            result = destination / (script.stem + suffix)
            if not result.is_file() or result.stat().st_size == 0:
                raise RuntimeError("Missing output " + str(result))
    return stats


def run(source, output, check_only=False):
    import matplotlib
    matplotlib.use("Agg")
    if not check_only:
        import mplhep
        _ = mplhep.style.ATLAS

    manifest, galleries, failures = [], [], []
    for process, analyses in ANALYSES.items():
        for analysis in analyses:
            source_dir = source / process / "01_four_way_common_MC_shapes" / analysis
            scripts = sorted(p for p in source_dir.glob("*.py")
                             if not p.name.endswith("__data.py"))
            if not scripts:
                failures.append("Missing Rivet plots in " + str(source_dir))
            names = []
            for script in scripts:
                try:
                    stats = render_one(script, output / process / analysis, check_only)
                    names.append(script.stem)
                    for label, scale in stats["scales"].items():
                        manifest.append((process, analysis, script.stem,
                                         stats["mode"], label, scale))
                except Exception as exc:
                    failures.append(f"{script}: {type(exc).__name__}: {exc}")
            galleries.append((process, analysis, names))

    if not check_only:
        output.mkdir(parents=True, exist_ok=True)
        with (output / "normalization_manifest.csv").open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["process", "analysis", "observable", "mode",
                             "sample", "source_integral_or_first_bin"])
            writer.writerows(manifest)
        page = ['<!DOCTYPE html><html><head><meta charset="utf-8">'
                '<title>AQP — Presentation shape plots</title></head><body>',
                '<h1>AQP V+jets — presentation-only shape comparisons</h1>',
                '<p>Ordinary histograms independently normalized to unit area. '
                'Statistical uncertainties and ratio panels scaled consistently. '
                'These are not rate measurements.</p>']
        for process, analysis, names in galleries:
            page.append(f'<h2>{html.escape(process)} / {html.escape(analysis)}</h2>')
            for name in names:
                rel = f"{process}/{analysis}/{name}"
                page.append(f'<details><summary>{html.escape(name)}</summary>'
                            f'<a href="{rel}.pdf">PDF</a><br>'
                            f'<img style="max-width:100%" loading="lazy" '
                            f'src="{rel}.png"></details>')
        page.append("</body></html>")
        (output / "index.html").write_text("\n".join(page), encoding="utf-8")

    print(f"PLOTS={len(manifest)//4} ERROR_COUNT={len(failures)} OUTPUT={output}")
    for failure in failures:
        print("ERROR:", failure)
    return int(bool(failures))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    raise SystemExit(run(args.source, args.output, args.check_only))


if __name__ == "__main__":
    main()
