#!/usr/bin/env python3
"""Read-only triage of suspicious MINT1 records after check_mint1_timings.py.

Run in the MG process configuration directory. Requires the per-target CSV
created by scripts/check_mint1_timings.py; never writes to production files.
Compatible with Python 3.8+.
"""
import argparse
import csv
import math
from collections import Counter
from pathlib import Path


def number(row, column):
    try:
        value = float(row.get(column, ""))
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--csv", default="mint1_timing_audit.csv")
    p.add_argument("--process-dir", default=None)
    p.add_argument("--tail", type=int, default=12,
                   help="Last lines from suspicious MINT1 logs (default 12)")
    p.add_argument("--max-targets", type=int, default=30,
                   help="Maximum suspect targets printed (default 30)")
    p.add_argument("--threshold", type=float, default=0.20,
                   help="Relative Condor/MINT mismatch threshold (default 0.20)")
    args = p.parse_args()

    source = Path(args.csv)
    if not source.is_file():
        p.error("CSV does not exist: %s; run check_mint1_timings.py first" % source)
    with source.open(newline="") as f:
        rows = list(csv.DictReader(f))
    if args.process_dir:
        proc = Path(args.process_dir)
    else:
        matches = [q for q in Path.cwd().glob("PROCNLO_*") if q.is_dir()]
        if len(matches) != 1:
            p.error("expected one PROCNLO_* directory; set --process-dir")
        proc = matches[0]

    counts = Counter()
    suspect = []
    for row in rows:
        reasons = []
        mint = number(row, "mint_seconds")
        fortran = number(row, "fortran_total_seconds")
        condor = number(row, "condor_clean_seconds")
        if condor is None:
            condor = number(row, "condor_last_attempt_seconds")
        ratio = number(row, "condor_over_mint")
        if mint is None:
            reasons.append("MINT1 time absent/unparseable")
            counts["missing_mint"] += 1
        elif mint <= 0:
            reasons.append("MINT1 time zero/negative")
            counts["zero_mint"] += 1
        elif mint <= 2:
            reasons.append("MINT1 time <=2 seconds")
            counts["short_mint"] += 1
        if fortran is None:
            reasons.append("Fortran Total timing absent")
            counts["missing_fortran"] += 1
        if condor is None:
            reasons.append("selected Condor duration absent")
            counts["missing_condor"] += 1
        elif condor <= 0:
            reasons.append("selected Condor duration zero/negative")
            counts["zero_condor"] += 1
        if ratio is not None and abs(ratio - 1.0) > args.threshold:
            reasons.append("Condor/MINT ratio %.3g" % ratio)
            counts["mismatched_ratio"] += 1

        # Flag numerical-completion indicators absent; this is not a physics
        # validity test, only a prompt for a more detailed audit.
        target = proc / "SubProcesses" / row["subprocess"] / row["GF"]
        log = target / "log_MINT1.txt"
        if not log.is_file():
            reasons.append("MINT1 file missing")
        elif log.stat().st_size == 0:
            reasons.append("MINT1 file empty")
        else:
            txt = log.read_text(errors="replace")
            if "Time in seconds:" not in txt:
                reasons.append("final Time in seconds marker absent")
            if "Thanks for using LHAPDF" not in txt:
                reasons.append("LHAPDF footer absent (advisory)")
        if reasons:
            suspect.append((len(reasons), row, reasons, log))

    print("Targets total:            %d" % len(rows))
    print("Targets flagged:          %d" % len(suspect))
    for label, key in [
        ("Missing MINT1 time", "missing_mint"),
        ("Zero MINT1 time", "zero_mint"),
        ("MINT1 <=2 seconds", "short_mint"),
        ("Missing Fortran total", "missing_fortran"),
        ("Missing Condor duration", "missing_condor"),
        ("Zero Condor duration", "zero_condor"),
        ("Condor/MINT mismatch", "mismatched_ratio"),
    ]:
        print("%-26s %d" % (label + ":", counts[key]))
    print()
    print("Suspicious targets (prioritizing number of anomalies):")
    suspect.sort(key=lambda item: (-item[0], item[1]["subprocess"], item[1]["GF"]))
    for _, row, reasons, log in suspect[:args.max_targets]:
        mint = number(row, "mint_seconds")
        condor = number(row, "condor_clean_seconds")
        if condor is None:
            condor = number(row, "condor_last_attempt_seconds")
        print("\n%s/%s  MINT=%s s  Condor=%s s" %
              (row["subprocess"], row["GF"], mint, condor))
        print("Flags: " + "; ".join(reasons))
        if args.tail and log.is_file():
            print("Last %d lines of log_MINT1.txt:" % args.tail)
            for line in log.read_text(errors="replace").splitlines()[-args.tail:]:
                print("  " + line[:250])

    if len(suspect) > args.max_targets:
        print("\n... %d additional flagged targets omitted." %
              (len(suspect) - args.max_targets))
    print("\nIMPORTANT: flags are diagnostic only. Missing a particular")
    print("timing/footer field does not prove physics failure. Compare")
    print("against the actual MG5_aMC@NLO 3.5.11 source and a known-good GF.")

if __name__ == "__main__":
    main()
