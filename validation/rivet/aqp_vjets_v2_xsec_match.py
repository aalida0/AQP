#!/usr/bin/env python3
"""Match old v2 AQP Rivet YODA to PanDA log.generate physical FxFx XS metadata.

READ-ONLY (except optional --output report). Requires no Athena, Rivet,
YODA, Rucio, or network; can run on AF login.

For each v2 configuration, matches by PanDA TASK and JOB number embedded
in both Rucio LFN and offline YODA names. Extracts post-FxFx
'MetaData: cross-section (nb)' and cross-checks the logged recipe.
Reports percentage of the existing YODA files covered by matched logs.

NOT a cross-section correction; do not use sampled pilot estimates as
full-production normalizations. No changes to existing YODA files.
"""
import argparse
import json
import math
import re
import statistics
from pathlib import Path

from aqp_vjets_generator_xsec_evidence import decode_log, log_paths
from aqp_vjets_physics_preflight import reference_path, scan_yoda

V2_SAMPLES = (
    ("Zee", "standard111"),
    ("Zee", "delta111"),
    ("Zee", "delta221"),
    ("Wenu", "delta111"),
    ("Wenu", "delta221"),
)
JOB_ID = re.compile(r"user[.]aalida[.](\d+)[.]_(\d+)")
RECIPE = re.compile(
    r"Using FxFx cross section recipe:\s*xs\s*=\s*"
    r"([+-]?\d+(?:[.]\d*)?(?:[eE][+-]?\d+)?)\s*/\s*"
    r"([+-]?\d+(?:[.]\d*)?(?:[eE][+-]?\d+)?)",
)
FINAL_XS = re.compile(
    r"MetaData:\s*cross-section\s*\(nb\)\s*=\s*"
    r"([+-]?\d+(?:[.]\d*)?(?:[eE][+-]?\d+)?)",
)


def job_key(path):
    match = JOB_ID.search(Path(path).name)
    return (match.group(1), int(match.group(2))) if match else None


def extract_xsec(log_text):
    """Return (xs_pb, xs_nb, recipe) only for complete, coherent log metadata."""
    xs = FINAL_XS.findall(log_text)
    recipe = RECIPE.findall(log_text)
    if not xs or not recipe:
        return None, "MISSING_POST_FXFX_METADATA_OR_RECIPE"
    try:
        xnb = float(xs[-1])
        numerator, denominator = (float(x) for x in recipe[-1])
        if not all(math.isfinite(v) for v in (xnb, numerator, denominator)):
            return None, "NONFINITE_XS"
        if not (xnb > 0 and numerator > 0 and denominator > 0):
            return None, "NONPOSITIVE_XS_OR_DENOMINATOR"
        calculated_nb = numerator/denominator * 1e6
        relative_difference = calculated_nb/xnb - 1
        if abs(relative_difference) > 0.01:
            return None, f"XS_RECIPE_MISMATCH_{relative_difference:.6g}"
        return {
            "xs_nb": xnb, "xs_pb": 1000*xnb,
            "recipe_numerator": numerator, "recipe_denominator": denominator,
            "recipe_calculated_nb": calculated_nb,
            "recipe_relative_difference": relative_difference,
        }, None
    except (ValueError, ZeroDivisionError, OverflowError):
        return None, "XS_PARSE_ERROR"


def survey_sample(root, old, new, process, cfg, max_logs=0):
    source_merged = reference_path(process, cfg, old, new)
    directory = source_merged.parent.parent / "yoda"
    files = sorted(p for p in directory.glob("*.yoda.gz") if p.is_file())
    logs_dir = root / process / cfg / "v2"
    logs = log_paths(logs_dir)
    selected = logs[:max_logs] if max_logs else logs
    by_id, duplicates, invalid_logs = {}, [], []
    for log in selected:
        key = job_key(log)
        if key is None:
            invalid_logs.append({"file": str(log), "error": "MISSING_TASK_JOB_ID"})
            continue
        try:
            xs, issue = extract_xsec(decode_log(log))
        except (OSError, ValueError, EOFError) as exc:
            xs, issue = None, type(exc).__name__ + ":" + str(exc)
        if xs is None:
            invalid_logs.append({"file": str(log), "error": issue})
            continue
        if key in by_id:
            duplicates.append({"task_job": key, "file": str(log)})
            continue
        by_id[key] = (xs, log)

    results, unmatched_yoda, invalid_yoda = [], [], []
    seen_ids = set()
    for yoda in files:
        key = job_key(yoda)
        if key is None or key in seen_ids:
            invalid_yoda.append({"file": str(yoda), "issue": "NO_OR_DUPLICATE_TASK_JOB_ID"})
            continue
        seen_ids.add(key)
        if key not in by_id:
            unmatched_yoda.append(str(yoda))
            continue
        info, log_path = by_id[key]
        meta = scan_yoda(yoda)
        if meta["error"]:
            invalid_yoda.append({"file": str(yoda), "issue": meta["error"]})
            continue
        xsec_info = next(
            (v for v in meta["metadata_blocks"] if v["path"] == "/RAW/_XSEC"), None)
        count_info = next(
            (v for v in meta["metadata_blocks"] if v["path"] == "/RAW/_EVTCOUNT"), None)
        if not xsec_info or not count_info:
            invalid_yoda.append({"file": str(yoda), "issue": "MISSING_RAW_METADATA"})
            continue
        try:
            old_xsec = float(xsec_info["sample_data_lines"][0].split()[0])
            columns = count_info["sample_data_lines"][0].split()
            sumw, entries = float(columns[0]), float(columns[2])
        except (ValueError, IndexError):
            invalid_yoda.append({"file": str(yoda), "issue": "INVALID_RAW_METADATA"})
            continue
        if not math.isclose(old_xsec, 1.0, abs_tol=1e-6):
            invalid_yoda.append({"file": str(yoda), "issue": "OLD_XSEC_NOT_DUMMY_1_PB"})
            continue
        if not (math.isfinite(sumw) and sumw != 0 and
                math.isfinite(entries) and entries > 0):
            invalid_yoda.append({"file": str(yoda), "issue": "INVALID_SUMW_OR_ENTRIES"})
            continue
        results.append({
            "task": key[0], "job": key[1],
            "log_file": str(log_path), "yoda_file": str(yoda),
            **info, "old_dummy_xs_pb": old_xsec,
            "yoda_sumW": sumw, "yoda_accepted_entries": entries,
        })
    paired_jobs = len(results)
    xs_values = [r["xs_pb"] for r in results]
    mean = statistics.mean(xs_values) if xs_values else None
    std = statistics.stdev(xs_values) if len(xs_values) > 1 else None
    # This is a diagnostic trial-weighted combination of the XSECs
    # encountered in the log/YODA pairs, NOT a certified production rate.
    denominator = sum(r["yoda_sumW"]/r["xs_pb"] for r in results)
    trials_xs = (
        sum(r["yoda_sumW"] for r in results)/denominator if denominator
        else None)
    return {
        "sample": f"{process}/{cfg}/v2",
        "yoda_directory": str(directory),
        "logs_directory": str(logs_dir),
        "n_yoda_files": len(files),
        "n_logs_available": len(logs),
        "n_logs_scanned": len(selected),
        "n_logs_valid_unique": len(by_id),
        "n_matched": paired_jobs,
        "fraction_yoda_covered": paired_jobs/len(files) if files else 0,
        "pilot_mean_xs_pb": mean, "pilot_sd_xs_pb": std,
        "paired_rivet_trials_xs_pb": trials_xs,
        "matched": results,
        "unmatched_yoda": unmatched_yoda,
        "invalid_yoda": invalid_yoda,
        "invalid_logs": invalid_logs,
        "duplicate_log_task_jobs": duplicates,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--logs-root", type=Path,
                   default=Path("/data/aalida/AQP/aqp_log_comparison"))
    p.add_argument("--old", type=Path, default=Path("/data/aalida/AQP_Rivet"))
    p.add_argument("--new", type=Path,
                   default=Path("/data/aalida/AQP_Rivet_full/outputs"))
    p.add_argument("--max-logs", type=int, default=0,
                   help="Per sample; 0=all locally present log files")
    p.add_argument("--sample", choices=[f"{p}/{c}" for p,c in V2_SAMPLES],
                   action="append", help="Only these samples; can repeat")
    p.add_argument("--output", type=Path, default=Path.home() /
                   "AQP/v2_log_yoda_xsec_match_20261123.json")
    args=p.parse_args()
    if args.max_logs < 0:
        p.error("--max-logs must be >=0")
    selected = (tuple(tuple(s.split("/")) for s in args.sample)
                if args.sample else V2_SAMPLES)
    summaries = [
        survey_sample(args.logs_root, args.old, args.new, proc, cfg,
                      max_logs=args.max_logs)
        for proc,cfg in selected
    ]
    result={"status":"READ_ONLY_JOB_MATCH_NOT_PHYSICS_CERTIFIED",
            "notes":[
                "Matched by task and job ID, not by file sequence.",
                "XS taken from post-FxFx generator Metadata (nb), then converted to pb.",
                "Original biased MG5 cross sections labeled DO NOT USE ignored.",
                "All 5 v2 YODA have dummy XS=1 pb; these are NOT physical.",
                "A small 10-log pilot must not be used to certify 2M-event rates.",
            ],
            "samples":summaries}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(f"{'sample':25} {'YODA':>5} {'logs':>5} {'paired':>6} "
          f"{'coverage':>9} {'xs_mean_pb':>13} {'xs_trials_pb':>13} {'invalid':>7}")
    print("-"*104)
    for r in summaries:
        fmt=lambda n: f"{n:.3f}" if n is not None else "NA"
        print(f"{r['sample']:25} {r['n_yoda_files']:>5} "
              f"{r['n_logs_scanned']:>5} {r['n_matched']:>6} "
              f"{r['fraction_yoda_covered']:>8.1%} "
              f"{fmt(r['pilot_mean_xs_pb']):>13} "
              f"{fmt(r['paired_rivet_trials_xs_pb']):>13} "
              f"{len(r['invalid_logs'])+len(r['invalid_yoda']):>7}")
    print(f"MATCH_REPORT={args.output}")
    print("PHYSICAL_XSEC_VALIDATED=NO")
    return 0 if all(r["n_matched"]>0 for r in summaries) else 1


if __name__=="__main__":
    raise SystemExit(main())
