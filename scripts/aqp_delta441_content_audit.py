#!/usr/bin/env python3
"""Read-only content comparison of active Wenu delta441 and historical backup.

Hashes mint_grids for all matching GF directories, plus the other three
integration artifacts in the backup's bad-real GF channels. --all-artifacts
hashes all four files for all GFs. Does not import MadGraph, call HTCondor,
touch logs or write integration files. No MINT success claims are inferred.
"""
import argparse
from collections import Counter
import hashlib
from pathlib import Path
import sys

from aqp_audit_wenu_condor_eventlogs import find_failed_mint1_gfs

PROC = "PROCNLO_loop_sm-no_b_mass_0"
FILES = ("mint_grids", "grid.MC_integer", "res.dat", "results.dat")


def gf_dirs(process):
    root = process / "SubProcesses"
    if not root.is_dir():
        raise ValueError("Missing SubProcesses: " + str(root))
    return {(gf.parent.name, gf.name): gf for gf in root.glob("P*/GF*")
            if gf.is_dir()}


def digest(path):
    """Return (hash, bytes), rejecting files changed during the read."""
    before = path.stat()
    if not path.is_file() or before.st_size == 0:
        return None, before.st_size
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("File changed during hash: " + str(path))
    return h.hexdigest(), after.st_size


def compare_file(before, after, do_hash):
    if not before.is_file() or not after.is_file():
        return "MISSING"
    bstat, astat = before.stat(), after.stat()
    if not bstat.st_size or not astat.st_size:
        return "EMPTY"
    if do_hash:
        bsha, _ = digest(before)
        asha, _ = digest(after)
        return "IDENTICAL" if bsha == asha else (
            "CHANGED_SIZE" if bstat.st_size != astat.st_size
            else "CHANGED_SAME_SIZE"
        )
    return ("SIZE_CHANGED_NOT_HASHED" if bstat.st_size != astat.st_size
            else "SAME_SIZE_NOT_HASHED")


def compare(base, all_artifacts=False):
    current = gf_dirs(base / "delta441" / PROC)
    backup_proc = base / "delta441_backup" / PROC
    previous = gf_dirs(backup_proc)
    bad = find_failed_mint1_gfs(backup_proc)
    common = sorted(set(current) & set(previous))
    report = {
        "current_gfs": len(current), "backup_gfs": len(previous),
        "common_gfs": len(common),
        "active_only": sorted(set(current) - set(previous)),
        "backup_only": sorted(set(previous) - set(current)),
        "backup_bad_real": len(bad),
        "backup_bad_missing_from_active": sorted(bad - set(current)),
        "all": {f: Counter() for f in FILES},
        "old_bad": {f: Counter() for f in FILES},
        "old_bad_details": [],
    }
    for gf in common:
        per_gf = {}
        for name in FILES:
            should_hash = all_artifacts or name == "mint_grids" or gf in bad
            status = compare_file(previous[gf] / name, current[gf] / name,
                                  should_hash)
            report["all"][name][status] += 1
            if gf in bad:
                report["old_bad"][name][status] += 1
                per_gf[name] = status
        if gf in bad:
            report["old_bad_details"].append(("/".join(gf), per_gf))
    return report


def print_report(r, all_artifacts):
    print("AQP DELTA441 ACTIVE / BACKUP CONTENT AUDIT (READ ONLY)")
    for name in ("current_gfs", "backup_gfs", "common_gfs",
                 "backup_bad_real", "active_only", "backup_only",
                 "backup_bad_missing_from_active"):
        value = r[name]
        print(name.upper(), value if not isinstance(value, list) else len(value))
        if isinstance(value, list) and value:
            print(" ", value[:15])
    print("MODE", "all_artifacts" if all_artifacts
          else "all_grids_plus_backup_bad_artifacts")
    for group in ("all", "old_bad"):
        print("===", group.upper(), "===")
        for f in FILES:
            print(f, dict(sorted(r[group][f].items())))
    print("=== PREVIOUSLY BAD-REAL GF CHANNELS ===")
    for name, statuses in r["old_bad_details"]:
        print(name, " ".join(f+"="+statuses[f] for f in FILES))
    print("IMPORTANT: identical byte content != numerically validated MINT.")
    print("Missing current MINT1 logs do not mean successful integration.")
    print("No integration, submission, scheduler query, or file modification.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, type=Path)
    parser.add_argument("--all-artifacts", action="store_true",
                        help="Hash all four artifact files in all 300 GF channels")
    args = parser.parse_args()
    if not args.base.is_dir():
        parser.error("Wenu base directory does not exist")
    try:
        result = compare(args.base, args.all_artifacts)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print_report(result, args.all_artifacts)


if __name__ == "__main__":
    main()
