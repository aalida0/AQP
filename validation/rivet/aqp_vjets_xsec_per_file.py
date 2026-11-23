#!/usr/bin/env python3
"""Trace merged Rivet XSEC to individual YODA files; read-only.

Samples up to N individual YODA files from Zee D441 v3, Wenu S111 v1
(corrected seed817263) and Wenu D441 v3. Also includes a v2 sample as
an artificial-XS control. A check on a sample of files is NOT a
certificate of the generator's physical cross section.
"""
import argparse
import csv
import json
import math
import statistics
from pathlib import Path

from aqp_vjets_physics_preflight import FILES, reference_path, scan_yoda

TARGETS = (
    ("Zee", "standard111"),
    ("Zee", "delta441"),
    ("Wenu", "standard111"),
    ("Wenu", "delta111"),
    ("Wenu", "delta441"),
)


def get_first(meta, name):
    paths = [f"/RAW/{name}", f"/{name}"]
    for p in paths:
        for obj in meta["metadata_blocks"]:
            if obj["path"] == p and obj["sample_data_lines"]:
                try:
                    return float(obj["sample_data_lines"][0].split()[0])
                except (ValueError, IndexError):
                    pass
    return None


def inspect(old, new, limit, targets=TARGETS):
    """limit=0 means inspect ALL available per-file YODA for selected sample(s)."""
    rows, aggregates = [], []
    for process, config in targets:
        merged = reference_path(process, config, old, new)
        folder = merged.parent.parent / "yoda"
        if not folder.is_dir():
            # Some original v2 campaigns use a different YODA layout.
            print(f"WARNING: per-file YODA directory unavailable: {folder}")
            continue
        files = sorted(p for p in folder.glob("*.yoda.gz") if p.is_file())
        if not files:
            print(f"WARNING: no per-file YODA found: {folder}")
            continue
        selected = files if limit == 0 else files[:limit]
        local = []
        nonpositive_sumw = 0
        for f in selected:
            meta = scan_yoda(f)
            xs = get_first(meta, "_XSEC")
            sw = get_first(meta, "_EVTCOUNT")
            # _EVTCOUNT uses sumW, sumW2, entries. Record the original
            # counter for diagnostics; do NOT replace negative signed sums
            # by absolute values.
            counter = next((obj["sample_data_lines"][0]
                            for obj in meta["metadata_blocks"]
                            if obj["path"] == "/RAW/_EVTCOUNT"
                            and obj["sample_data_lines"]), None)
            fields = counter.split() if counter else []
            try:
                sw2 = float(fields[1]) if len(fields) > 1 else None
                entries = float(fields[2]) if len(fields) > 2 else None
            except ValueError:
                sw2 = entries = None
            row = {
                "process": process, "config": config, "source": str(f),
                "xsec_pb": xs, "sumW": sw, "sumW2": sw2,
                "entries": entries, "error": meta["error"],
            }
            rows.append(row)
            if sw is not None and sw <= 0:
                nonpositive_sumw += 1
            # Respect signed event weights: a negative per-job sumW is
            # unusual but must not be silently discarded. A zero/negative
            # cross section is not usable for the trials reconstruction.
            if xs is not None and xs > 0 and sw is not None and sw != 0:
                local.append((xs, sw, sw2))
        merged_meta = scan_yoda(merged)
        merged_xs = get_first(merged_meta, "_XSEC")
        full_nevents = get_first(merged_meta, "_EVTCOUNT")
        if local:
            xs_sample = [x[0] for x in local]
            weighted = sum(x * w for x, w, _ in local) / sum(w for _, w, _ in local)
            # Rivet 4's equivalent merging estimates ntrials = sum(sumW_i/xsec_i)
            # and XS = total_sumW / ntrials; NOT the arithmetic mean.
            trials = sum(w / x for x, w, _ in local if x != 0)
            harmonic = (sum(w for _, w, _ in local) / trials) if trials else None
            neff_points = [(x, (w*w)/w2) for x,w,w2 in local if w2 is not None and w2 > 0]
            weighted_neff = (sum(x*n for x,n in neff_points)/sum(n for _,n in neff_points)
                             if neff_points else None)
            avg = statistics.mean(xs_sample)
            median = statistics.median(xs_sample)
            lo, hi = min(xs_sample), max(xs_sample)
            coefficient = (statistics.pstdev(xs_sample)/abs(avg)) if avg else None
            sorted_xs = sorted(xs_sample)
            p10 = sorted_xs[int((len(sorted_xs)-1)*0.1)]
            p90 = sorted_xs[int((len(sorted_xs)-1)*0.9)]
            n_low10k = sum(x < 10000 for x in xs_sample)
            n_lowhalf = sum(x < median/2 for x in xs_sample)
        else:
            weighted = weighted_neff = harmonic = median = lo = hi = coefficient = p10 = p90 = None
            n_low10k = n_lowhalf = 0
        complete = len(local) == len(files) and len(selected) == len(files)
        aggregates.append({
            "process": process, "config": config, "merged_file": str(merged),
            "merged_xsec_pb": merged_xs, "merged_sumW": full_nevents,
            "n_files_found": len(files), "n_files_checked": len(selected),
            "n_files_with_cross_section": len(local),
            "all_files_checked_and_valid": complete,
            "sample_xsec_weighted_avg_pb": weighted,
            "sample_xsec_rivet_equiv_pb": harmonic,
            "sample_xsec_neff_weighted_avg_pb": weighted_neff,
            "sample_xsec_median_pb": median,
            "sample_xsec_min_pb": lo, "sample_xsec_max_pb": hi,
            "sample_xsec_p10_pb": p10, "sample_xsec_p90_pb": p90,
            "n_xsec_below_10k_pb": n_low10k,
            "n_xsec_below_half_median": n_lowhalf,
            "n_nonpositive_sumW": nonpositive_sumw,
            "sample_xsec_cv": coefficient,
            "recomputed_sumW_all_valid_files": sum(w for _,w,_ in local),
            "fractional_difference_weighted_vs_merged": (
                (harmonic/merged_xs - 1)
                if complete and merged_xs not in (None, 0) else None),
        })
    return aggregates, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old", type=Path, default=Path("/data/aalida/AQP_Rivet"))
    parser.add_argument("--new", type=Path,
                        default=Path("/data/aalida/AQP_Rivet_full/outputs"))
    parser.add_argument("--max-files", type=int, default=20,
                        help="Number of per-file YODA to scan; 0=all files")
    parser.add_argument("--only", action="append", choices=[
        p + "/" + c for p, c in TARGETS
    ], help="Limit to one or more process/config; repeat as needed")
    parser.add_argument("--out", type=Path,
                        default=Path("/data/aalida/AQP_Rivet_full/outputs/"
                                     "xsec_per_file_pilot_20261123.json"))
    args = parser.parse_args()
    if args.max_files < 0:
        parser.error("--max-files must be >= 0")
    targets = tuple(tuple(x.split("/")) for x in args.only) if args.only else TARGETS
    reports, rows = inspect(args.old, args.new, args.max_files, targets=targets)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "status": "PER_FILE_XSEC_DIAGNOSTIC_ONLY_NOT_PHYSICS_CERTIFIED",
        "notes": [
            "Sample selection is deterministic (first filenames sorted) unless --max-files 0 uses all files.",
            "Rivet equivalent merge combines per-file XSEC with sumW weights.",
            "Rivet equivalent merging estimates XS = sum(sumW_i) / sum(sumW_i/XS_i).",
            "A sampled per-file average is not the full-file merged average.",
            "Old v2 CrossSection=1 pb is artificial by construction.",
            "Compare Wenu D441 to Wenu corrected S111 independently of this step.",
            "Do not change physical scale until cross-checked with generator logs.",
        ],
        "summary": reports, "per_file": rows,
    }, indent=2) + "\n")
    print(f"{'Sample':20} {'merged pb':>12} {'median pb':>12} "
          f"{'range pb':>26} {'checked':>9} {'CV %':>9}")
    print("-" * 96)
    for row in reports:
        fmt = lambda x: f"{x:.3f}" if x is not None else "NA"
        r = (f"{fmt(row['sample_xsec_min_pb'])}.."
             f"{fmt(row['sample_xsec_max_pb'])}")
        cv = (100*row["sample_xsec_cv"]
              if row["sample_xsec_cv"] is not None else None)
        print(f"{row['process']+'/'+row['config']:20} "
              f"{fmt(row['merged_xsec_pb']):>12} "
              f"{fmt(row['sample_xsec_median_pb']):>12} "
              f"{r:>26} "
              f"{str(row['n_files_with_cross_section'])+'/'+str(row['n_files_checked']):>9} "
              f"{fmt(cv):>9}")
    for item in reports:
        if item["all_files_checked_and_valid"]:
            print(f"FULL_AUDIT {item['process']}/{item['config']}: "
                  f"RIVET_EQUIV_XSEC_pb={item['sample_xsec_rivet_equiv_pb']:.6f} "
                  f"arithmetic_sumW_mean_pb={item['sample_xsec_weighted_avg_pb']:.6f} "
                  f"Neff_weighted_mean_pb={item['sample_xsec_neff_weighted_avg_pb']} "
                  f"merged_pb={item['merged_xsec_pb']} "
                  f"sumW_in_files={item['recomputed_sumW_all_valid_files']:.8g} "
                  f"sumW_merged={item['merged_sumW']} "
                  f"relative_diff_rivet_equiv_vs_merged={item['fractional_difference_weighted_vs_merged']:.6g} "
                  f"n_xsec_below_10k={item['n_xsec_below_10k_pb']} "
                  f"p10/p90={item['sample_xsec_p10_pb']}/{item['sample_xsec_p90_pb']}")
        else:
            print(f"SAMPLE_ONLY {item['process']}/{item['config']} "
                  f"checked={item['n_files_with_cross_section']}/{item['n_files_found']}")
    print(f"\nPILOT_XSEC_AUDIT={args.out}")
    print("PHYSICAL_XSEC_VALIDATED=NO")
    return 0 if reports else 1


if __name__ == "__main__":
    raise SystemExit(main())
