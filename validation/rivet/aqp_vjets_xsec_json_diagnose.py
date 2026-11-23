#!/usr/bin/env python3
"""Diagnose all-file Rivet cross-section mismatch from saved JSON (read-only).

Works without Rivet, YODA, Athena, numpy, or rescanning the 1,984 files.
Displays records excluded by the earlier XS validity filter and computes
several *diagnostic* ways to average XSECs. These are not substitutes
for confirming the installed Rivet 4.1.2 implementation or generator XS.
"""
import argparse
import json
import math
from pathlib import Path


def valid(row):
    x, w = row.get("xsec_pb"), row.get("sumW")
    return (x is not None and w is not None and
            math.isfinite(x) and math.isfinite(w) and x > 0 and w != 0)


def finite_num(x):
    return isinstance(x, (int, float)) and math.isfinite(x)


def analyze(report):
    rows = report["per_file"]
    if not rows:
        raise ValueError("No per-file rows in JSON")
    summaries = report.get("summary", [])
    summary = summaries[0] if summaries else {}
    included = [r for r in rows if valid(r)]
    excluded = [r for r in rows if not valid(r)]
    sign_neg = [r for r in included if r["sumW"] < 0]

    def weighted_mean(key):
        usable = [(r["xsec_pb"], r[key]) for r in included
                  if finite_num(r.get(key)) and r[key] > 0]
        den = sum(w for _, w in usable)
        return (sum(x*w for x, w in usable)/den if den else None,
                len(usable))

    signed_sumw = sum(r["sumW"] for r in included)
    signed_wmean = (sum(r["xsec_pb"]*r["sumW"] for r in included)/signed_sumw
                    if signed_sumw else None)
    ntrials_proxy = sum(r["sumW"]/r["xsec_pb"] for r in included)
    harmonic_proxy = signed_sumw/ntrials_proxy if ntrials_proxy else None

    entry_mean, entry_files = weighted_mean("entries")
    median_xsec = sorted(r["xsec_pb"] for r in included)[len(included)//2]
    merged = summary.get("merged_xsec_pb")
    sumw_merged = summary.get("merged_sumW")
    all_known_sw = [r["sumW"] for r in rows if finite_num(r.get("sumW"))]
    all_sw_total = sum(all_known_sw)
    sumw_ratio = all_sw_total/sumw_merged if sumw_merged else None

    result = {
        "n_total":len(rows),
        "n_valid":len(included),
        "n_excluded":len(excluded),
        "excluded":excluded,
        "n_negative_signed_sumW":len(sign_neg),
        "merged_xsec_pb":merged,
        "merged_sumW":sumw_merged,
        "sumW_all_known_files":all_sw_total,
        "sumW_all_over_merged":sumw_ratio,
        "sumW_valid_files":signed_sumw,
        "median_valid_xsec_pb":median_xsec,
        "min_valid_xsec_pb":min(r["xsec_pb"] for r in included),
        "max_valid_xsec_pb":max(r["xsec_pb"] for r in included),
        "xs_sumW_weighted_mean_pb":signed_wmean,
        "xs_event_count_weighted_mean_pb":entry_mean,
        "entries_usable":entry_files,
        "xs_harmonic_proxy_pb_NOT_RIVET_FORMULA":harmonic_proxy,
    }
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("json_path", type=Path)
    args=p.parse_args()
    report=json.loads(args.json_path.read_text())
    result=analyze(report)
    for k,v in result.items():
        if k == "excluded":
            print(f"EXCLUDED_FILES={len(v)}")
            for row in v:
                print("  source:",row.get("source"))
                print("  xsec_pb:",row.get("xsec_pb"),
                      "sumW:",row.get("sumW"),
                      "sumW2:",row.get("sumW2"),
                      "entries:",row.get("entries"),
                      "parse_error:",row.get("error"))
        else:
            print(f"{k}={v}")
    print("PHYSICAL_XSEC_VALIDATED=NO")


if __name__ == "__main__":
    main()
