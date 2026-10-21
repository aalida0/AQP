#!/usr/bin/env python3
"""Read-only validation of MINT1 completion and independent execution times.

Python 3.8+. Run from W+jets configuration directory containing PROCNLO_*.
"""
import argparse
import csv
import math
import re
from datetime import datetime
from pathlib import Path
from statistics import median

TIME_RE = re.compile(r"\bTime in seconds:\s*(\d+(?:\.\d+)?)")
TOTAL_RE = re.compile(r"\bTime spent in Total\s*:\s*(\d+(?:\.\d+)?)")
EVENT_RE = re.compile(
    r"^(000|001|004|005) \((\d+)\.(\d+)\.\d+\) "
    r"(\d{4}-\d{2}-\d{2}) (\d\d:\d\d:\d\d)"
)

def condor_duration(path):
    if not path.is_file():
        return None
    jobs = {}
    for line in path.read_text(errors="replace").splitlines():
        m = EVENT_RE.match(line)
        if not m:
            continue
        code, cluster, proc, date, clock = m.groups()
        jid = (int(cluster), int(proc))
        dt = datetime.strptime(date + " " + clock, "%Y-%m-%d %H:%M:%S")
        j = jobs.setdefault(jid, {"submit": None, "events": []})
        j["events"].append((code, dt))
        if code == "000" and j["submit"] is None:
            j["submit"] = dt
    candidates = []
    for jid, j in jobs.items():
        start = None
        last = None
        for code, dt in sorted(j["events"], key=lambda x: x[1]):
            if code == "001":
                start = dt
            elif code == "004":
                start = None
            elif code == "005":
                if start is not None:
                    last = (dt - start).total_seconds()
                start = None
        if j["submit"] is not None and last is not None:
            candidates.append((j["submit"], jid, last))
    return sorted(candidates)[0][-1] if candidates else None

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--process-dir")
    p.add_argument("--timing-dir", default="aqp_condor_timing")
    p.add_argument("--csv", default="mint1_crosscheck.csv")
    p.add_argument("--tolerance", type=float, default=0.20)
    a = p.parse_args()

    matches = sorted(Path.cwd().glob("PROCNLO_*"))
    if a.process_dir:
        process = Path(a.process_dir)
    elif len(matches) == 1:
        process = matches[0]
    else:
        p.error("Expected exactly one PROCNLO_*; set --process-dir")
    sub = process / "SubProcesses"
    if not sub.is_dir():
        p.error("SubProcesses directory not found: " + str(sub))

    rows = []
    for gf in sorted(sub.glob("P*/GF*")):
        if not gf.is_dir():
            continue
        issues = []
        log = gf / "log_MINT1.txt"
        seconds = total_seconds = None
        if log.is_file() and log.stat().st_size:
            content = log.read_text(errors="replace")
            times = TIME_RE.findall(content)
            totals = TOTAL_RE.findall(content)
            seconds = float(times[-1]) if times else None
            total_seconds = float(totals[-1]) if totals else None
        if seconds is None:
            issues.append("missing_final_MINT1_time")
        if total_seconds is None:
            issues.append("missing_fortran_total_time")
        if not (gf / "mint_grids").is_file() or not (gf / "mint_grids").stat().st_size:
            issues.append("missing_mint_grids")
        result = gf / "results.dat"
        if not result.is_file() or not result.stat().st_size:
            issues.append("missing_results_dat")
        else:
            try:
                vals = [float(t.replace("D", "E")) for t in result.read_text().split()]
                if not vals or not all(math.isfinite(v) for v in vals):
                    issues.append("nonfinite_results_dat")
            except ValueError:
                issues.append("unparseable_results_dat")

        timelog = Path(a.timing_dir) / (gf.parent.name + "__" + gf.name + "__step1.log")
        elapsed = condor_duration(timelog)
        ratio = elapsed / seconds if seconds and elapsed is not None else None
        if ratio is not None and abs(ratio - 1) > a.tolerance:
            issues.append("condor_MINT1_discrepancy")
        rows.append({
            "subprocess": gf.parent.name, "GF": gf.name,
            "mint_seconds": seconds, "fortran_total_seconds": total_seconds,
            "condor_last_attempt_seconds": elapsed,
            "condor_over_mint": ratio, "issues": ";".join(issues)
        })

    with open(a.csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)
    with_mint = [r["mint_seconds"] for r in rows if r["mint_seconds"] is not None]
    fortran = [r["fortran_total_seconds"] for r in rows if r["fortran_total_seconds"] is not None]
    condor = [r["condor_last_attempt_seconds"] for r in rows if r["condor_last_attempt_seconds"] is not None]
    paired = [r for r in rows if r["condor_over_mint"] is not None]
    mismatches = [r for r in paired if abs(r["condor_over_mint"] - 1) > a.tolerance]
    other = [r for r in rows if r["issues"] and r["issues"] != "condor_MINT1_discrepancy"]

    print("GF directories:                 ", len(rows))
    print("Complete MINT1 timing fields:   ", len(with_mint))
    print("Matched Condor timing records:  ", len(paired))
    print("Total MINT1 hours:               %.3f" % (sum(with_mint) / 3600))
    print("Total Fortran timing hours:      %.3f" % (sum(fortran) / 3600))
    print("Total selected Condor hours:     %.3f" % (sum(condor) / 3600))
    if paired:
        print("Median Condor/MINT1 ratio:       %.3f" % median(r["condor_over_mint"] for r in paired))
    print("Advisory timing mismatches:     ", len(mismatches))
    print("Other output anomalies:         ", len(other))
    for r in sorted(mismatches, key=lambda x: abs(x["condor_over_mint"] - 1), reverse=True)[:12]:
        print(" TIMING %-29s %-7s ratio=%.3f" %
              (r["subprocess"], r["GF"], r["condor_over_mint"]))
    for r in other[:12]:
        print(" OUTPUT %-29s %-7s %s" %
              (r["subprocess"], r["GF"], r["issues"]))
    print("Per-target details written to: ", a.csv)
    print("NOTE: MINT1 and Condor clocks measure different quantities;")
    print("differences are diagnostics, not automatic evidence of failed physics.")

if __name__ == "__main__":
    main()
