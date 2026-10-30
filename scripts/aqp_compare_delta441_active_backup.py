#!/usr/bin/env python3
"""Read-only Delta441 current vs backup integration audit.

The active process is WENU/delta441. delta441_backup is a historical snapshot;
never treat backup MINT1 errors as current. Checks presence/nonzero sizes,
log error markers, and per-GF file metadata (no expensive full grid hashing).

No Condor calls, MadGraph imports, file writes, or integration execution.
"""
import argparse
from collections import Counter
from datetime import datetime
from pathlib import Path

from aqp_audit_wenu_condor_eventlogs import (
    MAX_LOG_BYTES, MINT_RE, find_failed_mint1_gfs,
)

PROC = "PROCNLO_loop_sm-no_b_mass_0"
ARTIFACTS = ("mint_grids", "grid.MC_integer", "res.dat", "results.dat")


def gf_map(process):
    root = process / "SubProcesses"
    if not root.is_dir():
        raise ValueError("No SubProcesses directory: " + str(root))
    return {
        (gf.parent.name, gf.name): gf
        for gf in root.glob("P*/GF*") if gf.is_dir()
    }


def file_info(path):
    try:
        info = path.stat()
    except FileNotFoundError:
        return {"present": False, "nonempty": False, "bytes": 0, "mtime_ns": None}
    return {
        "present": path.is_file(),
        "nonempty": path.is_file() and info.st_size > 0,
        "bytes": info.st_size,
        "mtime_ns": info.st_mtime_ns,
    }


def log_status(folder):
    path = folder / "log_MINT1.txt"
    if not path.is_file():
        return "NO_LOG"
    if path.stat().st_size > MAX_LOG_BYTES:
        return "LOG_TOO_LARGE"
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "LOG_UNREADABLE"
    if MINT_RE.search(content):
        return "BAD_REAL"
    if "Fortran runtime error" in content:
        return "OTHER_FORTRAN_ERROR"
    return "NO_BAD_REAL_MARKER"


def summarize(source):
    gfs = gf_map(source)
    failures = find_failed_mint1_gfs(source)
    counts = Counter()
    artifact_counts = Counter()
    for key, folder in gfs.items():
        state = log_status(folder)
        counts[state] += 1
        if all(file_info(folder / name)["nonempty"] for name in ARTIFACTS):
            artifact_counts["four_files_nonempty"] += 1
        else:
            artifact_counts["missing_or_empty"] += 1
    return gfs, failures, counts, artifact_counts


def audit(base):
    current = base / "delta441" / PROC
    backup = base / "delta441_backup" / PROC
    cur_map, cur_bad, cur_state, cur_files = summarize(current)
    bak_map, bak_bad, bak_state, bak_files = summarize(backup)
    print("AQP DELTA441 ACTIVE VS BACKUP INTEGRATION AUDIT (READ ONLY)")
    print("ACTIVE", current)
    print("BACKUP", backup)
    for name, folders, errors, states, files in [
        ("ACTIVE_DELTA441", cur_map, cur_bad, cur_state, cur_files),
        ("HISTORICAL_BACKUP", bak_map, bak_bad, bak_state, bak_files),
    ]:
        print("===", name, "===")
        print("GF_DIRECTORIES", len(folders))
        print("BAD_REAL_MINT1", len(errors))
        print("MINT1_LOG_CLASSES", dict(states))
        print("FOUR_REQUIRED_FILES_NONEMPTY", files["four_files_nonempty"])
        print("MISSING_OR_EMPTY_REQUIRED_FILES", files["missing_or_empty"])
    only_active = sorted(set(cur_map) - set(bak_map))
    only_backup = sorted(set(bak_map) - set(cur_map))
    print("GF_ONLY_IN_ACTIVE", len(only_active))
    print("GF_ONLY_IN_BACKUP", len(only_backup))
    if only_active:
        print("EXAMPLE_ONLY_ACTIVE", only_active[:10])
    if only_backup:
        print("EXAMPLE_ONLY_BACKUP", only_backup[:10])
    print("BACKUP_BAD_REAL_STATUS_IN_ACTIVE")
    transitions = Counter()
    for key in sorted(bak_bad):
        label = "/".join(key)
        if key not in cur_map:
            status = "MISSING_GF_IN_ACTIVE"
        else:
            status = log_status(cur_map[key])
        transitions[status] += 1
        print(label, "backup=BAD_REAL", "active=" + status)
        if key in cur_map:
            for fname in ARTIFACTS:
                before = file_info(bak_map[key] / fname)
                after = file_info(cur_map[key] / fname)
                print(" ", fname,
                      "backup_nonempty=" + str(before["nonempty"]),
                      "active_nonempty=" + str(after["nonempty"]),
                      "size_changed=" + str(before["bytes"] != after["bytes"]),
                      "mtime_changed=" + str(before["mtime_ns"] != after["mtime_ns"]))
    print("BACKUP_BAD_REAL_ACTIVE_STATES", dict(transitions))
    new = sorted(cur_bad - bak_bad)
    print("ACTIVE_BAD_REAL_ABSENT_FROM_BACKUP", len(new))
    if new:
        print("NEW_ACTIVE_BAD_REAL_EXAMPLES", ["/".join(k) for k in new[:20]])
    timing = base / "delta441/aqp_condor_timing"
    print("ACTIVE_TIMING_DIRECTORY", str(timing), "exists=" + str(timing.is_dir()))
    if timing.is_dir():
        print("ACTIVE_TIMING_LOG_COUNT", len(list(timing.glob("*.log"))))
    print("LIMITATION: no bad-real marker != successful integration.")
    print("Presence, file size and modification time do not prove numerical integrity.")
    print("No files modified, no Condor queries or job submissions.")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", type=Path, required=True)
    args = p.parse_args()
    if not args.base.is_dir():
        p.error("Missing Wenu base directory")
    try:
        audit(args.base)
    except (ValueError, OSError) as exc:
        p.error(str(exc))


if __name__ == "__main__":
    main()
