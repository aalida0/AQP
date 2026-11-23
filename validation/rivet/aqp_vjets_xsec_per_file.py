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


def inspect(old, new, limit):
    rows, aggregates = [], []
    for process, config in TARGETS:
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
        selected = files[:limit]
        local = []
        for f in selected:
            meta = scan_yoda(f)
            xs = get_first(meta, "_XSEC")
            sw = get_first(meta, "_EVTCOUNT")
            row = {
                "process": process, "config": config, "source": str(f),
                "xsec_pb": xs, "sumW": sw, "error": meta["error"],
            }
            rows.append(row)
            if xs is not None and sw is not None and sw > 0:
                local.append((xs, sw))
        merged_meta = scan_yoda(merged)
        merged_xs = get_first(merged_meta, "_XSEC")
        full_nevents = get_first(merged_meta, "_EVTCOUNT")
        if local:
            xs_sample = [x[0] for x in local]
            weighted = sum(x * w for x, w in local) / sum(w for x, w in local)
            avg = statistics.mean(xs_sample)
            median = statistics.median(xs_sample)
            lo, hi = min(xs_sample), max(xs_sample)
            coefficient = (statistics.pstdev(xs_sample)/abs(avg)) if avg else None
        else:
            weighted = median = lo = hi = coefficient = None
        aggregates.append({
            "process": process, "config": config, "merged_file": str(merged),
            "merged_xsec_pb": merged_xs, "merged_sumW": full_nevents,
            "n_files_found": len(files), "n_files_checked": len(selected),
            "n_files_with_cross_section": len(local),
            "sample_xsec_weighted_avg_pb": weighted,
            "sample_xsec_median_pb": median,
            "sample_xsec_min_pb": lo, "sample_xsec_max_pb": hi,
            "sample_xsec_cv": coefficient,
        })
    return aggregates, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old", type=Path, default=Path("/data/aalida/AQP_Rivet"))
    parser.add_argument("--new", type=Path,
                        default=Path("/data/aalida/AQP_Rivet_full/outputs"))
    parser.add_argument("--max-files", type=int, default=20)
    parser.add_argument("--out", type=Path,
                        default=Path("/data/aalida/AQP_Rivet_full/outputs/"
                                     "xsec_per_file_pilot_20261123.json"))
    args = parser.parse_args()
    if args.max_files < 1:
        parser.error("--max-files must be positive")
    reports, rows = inspect(args.old, args.new, args.max_files)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "status": "PER_FILE_XSEC_DIAGNOSTIC_ONLY_NOT_PHYSICS_CERTIFIED",
        "notes": [
            "Sample selection is deterministic (first filenames sorted).",
            "Rivet equivalent merge combines per-file XSEC with sumW weights.",
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
    print(f"\nPILOT_XSEC_AUDIT={args.out}")
    print("PHYSICAL_XSEC_VALIDATED=NO")
    return 0 if reports else 1


if __name__ == "__main__":
    raise SystemExit(main())
