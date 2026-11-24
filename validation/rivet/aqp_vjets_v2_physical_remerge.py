#!/usr/bin/env python3
"""Non-destructively re-finalize v2 YODA using matched post-FxFx cross sections.

Uses Rivet 4.1.2's per-input 'file.yoda.gz:=xs_pb' override with
'rivet-merge -e'. No original files are edited. This is a normalization
metadata check, not certification of the physical rate.
"""
import argparse
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

VALID = {
    "Zee/standard111/v2", "Zee/delta111/v2", "Zee/delta221/v2",
    "Wenu/delta111/v2", "Wenu/delta221/v2",
}


def prepare(report, sample, limit=0, check_paths=True):
    if sample not in VALID or limit < 0:
        raise ValueError("Invalid sample or file limit")
    matches = [r for r in report["samples"] if r["sample"] == sample]
    if len(matches) != 1:
        raise ValueError("Expected exactly one matching sample")
    entry = matches[0]
    rows = entry["matched"]
    if (len(rows) != entry["n_yoda_files"] or
            entry["n_matched"] != entry["n_yoda_files"] or
            entry["n_logs_valid_unique"] != entry["n_yoda_files"] or
            any(entry[k] for k in ("unmatched_yoda", "invalid_yoda",
                                   "invalid_logs", "duplicate_log_task_jobs"))):
        raise ValueError("Incomplete or ambiguous generator-log pairing")
    rows = sorted(rows, key=lambda r: (r["task"], r["job"]))
    keys, paths = set(), set()
    for r in rows:
        key = (r["task"], r["job"])
        name = r["yoda_file"]
        xs, sw = r["xs_pb"], r["yoda_sumW"]
        if key in keys or name in paths:
            raise ValueError("Duplicate task/job or YODA path")
        keys.add(key)
        paths.add(name)
        if check_paths and not Path(name).is_file():
            raise FileNotFoundError(name)
        if (not all(math.isfinite(x) for x in (xs, sw)) or
                xs <= 0 or sw <= 0 or r["yoda_accepted_entries"] <= 0 or
                r["old_dummy_xs_pb"] != 1.0 or
                not math.isclose(xs, 1000*r["xs_nb"], rel_tol=1e-9)):
            raise ValueError("Invalid XS, sumW, event count, or original dummy 1 pb XS")
    # Independently reproduce the full-file cross-section in the match report.
    sw_full = sum(r["yoda_sumW"] for r in rows)
    trials_full = sum(r["yoda_sumW"]/r["xs_pb"] for r in rows)
    if not math.isclose(sw_full/trials_full, entry["paired_rivet_trials_xs_pb"],
                        rel_tol=1e-10):
        raise ValueError("Full cross-section reconstruction disagrees with JSON")
    selected = rows[:limit] if limit else rows
    sw = sum(r["yoda_sumW"] for r in selected)
    trials = sum(r["yoda_sumW"]/r["xs_pb"] for r in selected)
    nev = sum(r["yoda_accepted_entries"] for r in selected)
    args = [f'{r["yoda_file"]}:={r["xs_pb"]:.15g}' for r in selected]
    return args, sw/trials, sw, nev, len(rows)


def yoda_metadata(path):
    from aqp_vjets_physics_preflight import scan_yoda
    from aqp_vjets_xsec_per_file import get_first
    meta = scan_yoda(path)
    if meta["error"]:
        raise ValueError("Invalid merged YODA: " + meta["error"])
    xsec = get_first(meta, "_XSEC")
    evt = next((b["sample_data_lines"][0] for b in meta["metadata_blocks"]
                if b["path"] == "/RAW/_EVTCOUNT" and b["sample_data_lines"]), None)
    if not evt:
        raise ValueError("Missing /RAW/_EVTCOUNT")
    fields = evt.split()
    return xsec, float(fields[0]), float(fields[2])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report", type=Path, default=Path.home() /
                   "AQP/v2_log_yoda_xsec_match_FULL.json")
    p.add_argument("--sample", required=True, choices=sorted(VALID))
    p.add_argument("--max-files", type=int, default=0,
                   help="0=all; 2 for a small pilot")
    p.add_argument("--outdir", type=Path, default=Path(
        "/data/aalida/AQP_Rivet_full/outputs/v2_physical_xsec_20261124"))
    p.add_argument("--logdir", type=Path, default=Path.cwd(),
                   help="Condor scratch or /home, not Ceph /data")
    p.add_argument("--execute", action="store_true",
                   help="Run Rivet (otherwise read-only preflight)")
    a = p.parse_args()
    try:
        report = json.loads(a.report.expanduser().read_text())
        args, xs, sw, nev, total = prepare(report, a.sample, a.max_files)
    except (OSError, KeyError, TypeError, ValueError) as exc:
        p.error(str(exc))
    name = a.sample.replace("/", "_")
    name += f"_pilot{len(args)}" if a.max_files else "_full"
    outdir = a.outdir.expanduser().resolve()
    dest = outdir / (name + ".yoda.gz")
    if any(outdir == Path(f.split(":=")[0]).resolve().parent or
           Path(f.split(":=")[0]).resolve().parent in outdir.parents for f in args):
        p.error("Output directory must be outside original per-job YODA directories")
    print(f"SAMPLE={a.sample} MATCHED={len(args)}/{total}")
    print(f"EXPECTED_XSEC_PB={xs:.9f} EXPECTED_SUMW={sw:.12g} EXPECTED_ENTRIES={nev:g}")
    print(f"OUTPUT={dest}")
    if not a.execute:
        print("DRY_RUN_ONLY=YES")
        return 0
    if not shutil.which("rivet-merge"):
        p.error("Rivet unavailable; source LCG_108a_ATLAS_9 first")
    logdir = a.logdir.expanduser().resolve()
    if logdir == Path("/data") or Path("/data") in logdir.parents:
        p.error("Runtime logs must not be on Ceph /data")
    if dest.exists():
        p.error("Output already exists; refusing overwrite")
    outdir.mkdir(parents=True, exist_ok=True)
    logdir.mkdir(parents=True, exist_ok=True)
    stdout = logdir / (name + ".stdout.log")
    stderr = logdir / (name + ".stderr.log")
    with stdout.open("w") as fo, stderr.open("w") as fe:
        rc = subprocess.run(["rivet-merge", "-e", "-o", str(dest), *args],
                            stdout=fo, stderr=fe, check=False).returncode
    if rc:
        print(f"MERGE_FAILED={rc} LOG={stderr}", file=sys.stderr)
        return rc
    try:
        got_xs, got_sw, got_nev = yoda_metadata(dest)
        valid = (got_xs is not None and
                 math.isclose(got_xs, xs, rel_tol=5e-4) and
                 math.isclose(got_sw, sw, rel_tol=1e-4) and
                 math.isclose(got_nev, nev, rel_tol=1e-9))
    except (ValueError, TypeError, IndexError) as exc:
        print(f"METADATA_CHECK_FAILED={exc}", file=sys.stderr)
        return 1
    print(f"ACTUAL_XSEC_PB={got_xs} ACTUAL_SUMW={got_sw} ACTUAL_ENTRIES={got_nev}")
    print("REMERGE_METADATA=" + ("PASS" if valid else "FAIL"))
    print("PHYSICAL_XSEC_VALIDATED=NO")
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
