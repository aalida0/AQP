#!/usr/bin/env python3
"""Read-only diagnosis of failed MG5_aMC NLO scale/PDF reweighting.

Usage: python3 scripts/diagnose_gridpack_reweight.py ~/gridpack-validation/zee1jet.XXXX
Never modifies or deletes the gridpack, work directory, or logs.
"""
import argparse
from pathlib import Path
import re

ISSUE = re.compile(
    r"(?:error|failed|fatal|traceback|exception|not found|not available|"
    r"no such file|cannot|unable|invalid|abort|segmentation|lhapdf|"
    r"missing|stop\s+\d+)", re.IGNORECASE
)
CARD = re.compile(
    r"(?:lhaid|pdf|reweight|systematic|sys_|scale|dynamical_scale_choice)",
    re.IGNORECASE
)


def tail(path, n):
    return path.read_text(errors="replace").splitlines()[-n:]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path, help="Failed validation directory")
    parser.add_argument("--max-logs", type=int, default=8)
    parser.add_argument("--tail", type=int, default=50)
    parser.add_argument("--focus", default="P1_gd_demep/GF4.0",
                        help="Prioritize this subprocess/GF directory from the error")
    args = parser.parse_args()
    if args.max_logs < 1 or args.tail < 1:
        parser.error("--max-logs and --tail must be positive")
    run = args.run.expanduser().resolve(strict=True)
    subprocesses = run / "madevent" / "SubProcesses"
    if not subprocesses.is_dir():
        parser.error("No madevent/SubProcesses directory in " + str(run))
    print("RUN", run)
    print("MODE read-only; no generation or cleanup")

    logs = sorted(subprocesses.rglob("reweight_xsec_events.output"))
    print("REWEIGHT_LOG_FILES", len(logs))
    missing = [p for p in logs if not (p.parent / "events.lhe.rwgt").is_file()]
    print("REWEIGHT_LOGS_WITHOUT_EVENTS_LHE_RWGT", len(missing))
    exceptions = [p for p in logs if ISSUE.search(p.read_text(errors="replace"))]
    print("REWEIGHT_LOGS_WITH_DIAGNOSTIC_WORDS", len(exceptions))

    # Show logs with failed/missing outputs first; the outer 'completed'
    # count is not evidence that the reweighting binary succeeded.
    candidates = []
    seen = set()
    focused = [p for p in logs if args.focus in str(p.parent)]
    print("FOCUSED_REWEIGHT_LOGS", len(focused), "TARGET", args.focus)
    for p in focused + missing + exceptions + logs:
        if p not in seen:
            candidates.append(p)
            seen.add(p)
    for p in candidates[:args.max_logs]:
        print("\n===== REWEIGHT LOG", p.relative_to(run), "=====")
        lines = tail(p, args.tail)
        print("\n".join(lines) if lines else "[EMPTY LOG]")
        if not (p.parent / "events.lhe.rwgt").is_file():
            print("MISSING_OUTPUT", p.parent / "events.lhe.rwgt")
        nearby = sorted(
            x.name for x in p.parent.iterdir()
            if "reweight" in x.name.lower() or x.name.endswith(".rwgt")
        )
        print("NEARBY_REWEIGHT_FILES", ", ".join(nearby[:30]))

    if not logs:
        # Some gridpacks name the output differently. Inspect filenames
        # rather than concluding that no reweighting happened.
        others = list(subprocesses.rglob("*reweight*"))
        print("OTHER_REWEIGHT_PATHS", len(others))
        for p in others[:30]:
            print("PATH", p.relative_to(run))

    for name in ("run_card.dat", "reweight_card.dat"):
        path = run / "madevent" / "Cards" / name
        print("\n===== CARD", path, "=====")
        if not path.is_file():
            print("MISSING")
            continue
        matches = [line for line in path.read_text(errors="replace").splitlines()
                   if CARD.search(line) and not line.lstrip().startswith("#")]
        for line in matches[:55]:
            print(line[:240])

    print("\nDIAGNOSIS_COMPLETE: paste the REWEIGHT LOG and CARD sections.")
    print("No JobOption fix should be attempted until the worker error is known.")


if __name__ == "__main__":
    main()
