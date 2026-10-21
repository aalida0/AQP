#!/usr/bin/env python3
"""Read-only audit of suspect MINT1 outputs for W+jets recovery (Python >=3.8).

Usage:
    python3 audit_mint1_recovery.py ~/AQP/Wjets/WENU
Creates one CSV in the current directory. Does not modify MG process files.
"""
import argparse
import csv
import re
from collections import Counter
from pathlib import Path

CONFIGS = ("standard111", "delta111", "delta221", "delta441_backup")
TOTAL = re.compile(r"(?m)^\s*Time spent in Total\s*:\s*([-+0-9.eEdD]+)")
WALL = re.compile(r"(?m)^\s*Time in seconds:\s*([-+0-9.]+)")
EXCEPTION = re.compile(
    r"(?im)^.*(?:Program received signal|Fortran runtime error:|"
    r"Backtrace for this error|Segmentation fault|Floating point exception|"
    r"SIGSEGV|SIGFPE|SIGBUS|SIGILL).*$"
)

def inspect(path):
    if not path.is_file() or path.stat().st_size == 0:
        return {"present": False, "total": False, "wall": None,
                "crash_marker": False, "reason": "file missing or empty",
                "size": 0}
    data = path.read_text(errors="replace")
    totals = TOTAL.findall(data)
    times = WALL.findall(data)
    errors = list(EXCEPTION.finditer(data))
    signal_lines = [
        m.group(0).strip() for m in errors
        if "Backtrace for this error" not in m.group(0)
    ]
    reason = signal_lines[-1][:250] if signal_lines else (
        "Backtrace for this error (signal line not found)"
        if errors else ""
    )
    wall = None
    if times:
        try:
            wall = float(times[-1])
        except ValueError:
            pass
    return {"present": True, "total": bool(totals), "wall": wall,
            "crash_marker": bool(errors), "reason": reason,
            "size": path.stat().st_size}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("base", nargs="?", default=str(Path.home() / "AQP/Wjets/WENU"),
                   help="Directory containing standard111, delta111, delta221, delta441_backup")
    p.add_argument("--csv", default="wjets_mint1_recovery_audit.csv",
                   help="Output CSV (written only to current working directory)")
    args = p.parse_args()
    base = Path(args.base).expanduser()
    rows = []
    for cfg in CONFIGS:
        procs = sorted(q for q in (base / cfg).glob("PROCNLO_*") if q.is_dir())
        if len(procs) != 1:
            print("WARNING: %s: expected 1 process directory; found %d" %
                  (cfg, len(procs)))
            continue
        gfdirs = sorted(q for q in (procs[0] / "SubProcesses").glob("P*/GF*")
                        if q.is_dir())
        flags = Counter()
        for gf in gfdirs:
            actual = inspect(gf / "log_MINT1.txt")
            alias = inspect(gf / "log.txt")
            suspect = (not actual["present"] or not actual["total"]
                       or actual["crash_marker"]
                       or actual["wall"] is None or actual["wall"] <= 1)
            if not actual["present"]:
                flags["missing"] += 1
            if not actual["total"]:
                flags["missing_total"] += 1
            if actual["crash_marker"]:
                flags["crash_marker"] += 1
            if actual["wall"] is not None and actual["wall"] <= 1:
                flags["short"] += 1
            if suspect:
                flags["suspect"] += 1
                # log.txt can belong to a later step (e.g. event generation).
                # It is not evidence of successful MINT1.
                different = False
                if alias["present"] and actual["present"]:
                    different = (gf / "log.txt").read_bytes() != (
                        gf / "log_MINT1.txt").read_bytes()
                other_phase_log_has_total = different and alias["total"] and not alias["crash_marker"]
                rows.append({
                    "configuration": cfg,
                    "subprocess": gf.parent.name,
                    "GF": gf.name,
                    "mint1_wall_seconds": actual["wall"],
                    "has_fortran_total": actual["total"],
                    "has_crash_marker": actual["crash_marker"],
                    "error_or_signal": actual["reason"],
                    "log_txt_has_total_phase_unverified": other_phase_log_has_total,
                    "results_dat_nonempty": (
                        (gf / "results.dat").is_file()
                        and (gf / "results.dat").stat().st_size > 0),
                    "mint_grids_nonempty": (
                        (gf / "mint_grids").is_file()
                        and (gf / "mint_grids").stat().st_size > 0),
                    "mint1_mtime": (
                        (gf / "log_MINT1.txt").stat().st_mtime
                        if actual["present"] else None)
                })
        print("%s: GF=%d suspect=%d missing_fortran_total=%d "
              "backtrace_or_signal=%d missing=%d 0_or_1sec=%d" %
              (cfg, len(gfdirs), flags["suspect"], flags["missing_total"],
               flags["crash_marker"], flags["missing"], flags["short"]))
    keys = ("configuration", "subprocess", "GF", "mint1_wall_seconds",
            "has_fortran_total", "has_crash_marker", "error_or_signal",
            "log_txt_has_total_phase_unverified", "results_dat_nonempty",
            "mint_grids_nonempty", "mint1_mtime")
    with open(args.csv, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)
    print("\nSUSPECT TARGETS:")
    for row in rows:
        print("%-16s %-29s %-6s %8s s | %-65s | log_txt_has_total_phase_unverified=%s" %
              (row["configuration"], row["subprocess"], row["GF"],
               str(row["mint1_wall_seconds"]), row["error_or_signal"][:65],
               row["log_txt_has_total_phase_unverified"]))
    print("\nCSV: %s (%d targets)" % (args.csv, len(rows)))
    print("NOTE: log.txt may be from a later phase; it does not certify MINT1 success.")
    print("This audit identifies suspicious files, not the cause of failure.")
    print("Never overwrite or recompute a GF based only on these flags.")

if __name__ == "__main__":
    main()
