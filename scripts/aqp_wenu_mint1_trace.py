#!/usr/bin/env python3
"""Read-only Wenu MINT1 duplicate-submission timelines; no Condor calls."""
import argparse
from collections import Counter
from pathlib import Path
import re
from aqp_audit_wenu_condor_eventlogs import (
    CONFIGS, FILE_RE, EVENT_RE, RETURN_RE, MAX_LOG_BYTES,
    find_failed_mint1_gfs,
)

def parse(path):
    if path.stat().st_size > MAX_LOG_BYTES:
        raise ValueError("Oversized log")
    events = []
    for line in path.read_text(errors="replace").splitlines():
        m = EVENT_RE.match(line)
        if m:
            event, cid, proc, _ = m.groups()
            events.append([event, str(int(cid))+"."+str(int(proc)),
                           line[m.end():].strip()[:18], None])
        elif events and events[-1][0] == "005":
            code = RETURN_RE.search(line)
            if code:
                events[-1][3] = int(code.group(1))
    return events

def report(base):
    for config, timing_label in CONFIGS.items():
        timing = base / timing_label / "aqp_condor_timing"
        process = base / config / "PROCNLO_loop_sm-no_b_mass_0"
        bad = find_failed_mint1_gfs(process)
        duplicates = Counter()
        pairs = Counter()
        matched = 0
        print("===", config, "bad_real_gfs", len(bad), "===")
        if not timing.is_dir():
            print("NO_TIMING_DIRECTORY; evidence unavailable")
            continue
        for f in sorted(timing.glob("*.log")):
            fm = FILE_RE.fullmatch(f.name)
            if not fm:
                continue
            stage = fm.group("stage")
            ev = parse(f)
            submits = list(dict.fromkeys(x[1] for x in ev if x[0] == "000"))
            if len(submits) > 1:
                duplicates[stage] += 1
            if stage != "1":
                continue
            gf = (fm.group("subproc"), "GF"+fm.group("gf"))
            if gf not in bad:
                continue
            matched += 1
            first = submits[0] if submits else None
            newer = submits[1] if len(submits)>1 else None
            if newer:
                new_pos = next(i for i,x in enumerate(ev) if x[0]=="000" and x[1]==newer)
                term = [i for i,x in enumerate(ev) if x[1]==first and x[0] in ("005","009")]
                order = ("previous_terminated_before_next_submit"
                         if term and max(term)<new_pos else
                         "next_submitted_before_previous_terminal"
                         if term and min(term)>new_pos else "ambiguous_or_no_terminal")
                pairs[order] += 1
            print("BAD_REAL", "/".join(gf), "submit_ids", ",".join(submits))
            for code, job, stamp, rc in ev:
                if code in ("000","001","004","005","009","012","013"):
                    print(" ", stamp, code, job, "rc="+str(rc) if rc is not None else "")
        print("duplicate_logs_by_stage", dict(duplicates))
        print("bad_real_step1_logs", matched, "submit_order", dict(pairs))
    print("Interpretation: log record order, not proof of overlapping execution.")
    print("No files changed and no scheduler queries.")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", required=True, type=Path)
    args=p.parse_args()
    if not args.base.is_dir():
        p.error("Missing base directory")
    report(args.base)

if __name__ == "__main__":
    main()
