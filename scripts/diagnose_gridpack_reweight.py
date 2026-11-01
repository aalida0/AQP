#!/usr/bin/env python3
"""Read-only diagnosis of failed MG5_aMC NLO scale/PDF reweighting.

Usage: python3 scripts/diagnose_gridpack_reweight.py ~/gridpack-validation/zee1jet.XXXX
Never modifies or deletes the gridpack, work directory, or logs.
"""
import argparse
import gzip
from pathlib import Path
import re

ISSUE = re.compile(
    r"(?:error|failed|fatal|traceback|exception|not found|not available|"
    r"no such file|cannot|unable|invalid|abort|segmentation|lhapdf|"
    r"missing|stop\s+\d+)", re.IGNORECASE
)
CARD = re.compile(
    r"(?:lhaid|pdf|reweight|systematic|sys_|scale|store_rwgt_info|dynamical_scale_choice)",
    re.IGNORECASE
)


def tail(path, n):
    return path.read_text(errors="replace").splitlines()[-n:]


def inspect_first_event(path):
    """Report the first LHE event layout without modifying the file."""
    print("FIRST_EVENT_FILE", path)
    opener = gzip.open if path.suffix == ".gz" else open
    try:
        with opener(path, "rt", errors="replace") as stream:
            for lineno, line in enumerate(stream, 1):
                if "<event" in line:
                    break
                if lineno > 200000:
                    print("FIRST_EVENT_NOT_FOUND in 200000 header lines")
                    return
            else:
                print("FIRST_EVENT_NOT_FOUND")
                return

            event_header = stream.readline()
            fields = event_header.split()
            print("FIRST_EVENT_HEADER", repr(event_header[:260]))
            if not fields or not fields[0].isdigit():
                print("FIRST_EVENT_FORMAT_UNEXPECTED")
                return
            nup = int(fields[0])
            if not (1 <= nup <= 500):
                print("FIRST_EVENT_INVALID_NUP", nup)
                return
            print("FIRST_EVENT_NUP", nup)
            for _ in range(nup):
                if not stream.readline():
                    print("FIRST_EVENT_TRUNCATED_PARTICLES")
                    return

            next_lines = [stream.readline() for _ in range(6)]
            print("FIRST_EVENT_AFTER_PARTICLES_BEGIN")
            for i, event_line in enumerate(next_lines, 1):
                print(f"  line_{i}:", repr(event_line[:320]))
            print("FIRST_EVENT_AFTER_PARTICLES_END")
            first = next_lines[0]
            print("FIRST_EVENT_HAS_AMCATNLO_RECORD",
                  first.lstrip().startswith("#aMCatNLO"))
            print("FIRST_EVENT_RECORD_AT_COLUMN_ZERO",
                  first.startswith("#aMCatNLO"))
            if first.lstrip().startswith("#aMCatNLO"):
                fields = first.split()
                print("FIRST_EVENT_REWEIGHT_INFO_FIELD",
                      fields[8] if len(fields) > 8 else "MISSING")
    except (OSError, UnicodeError, EOFError, ValueError) as error:
        print("FIRST_EVENT_INSPECTION_ERROR", repr(error))


def inspect_gf_events(run, focused_logs):
    print("\n===== RAW SUBPROCESS LHE EVENT AUDIT =====")
    if not focused_logs:
        print("NO_MATCHING_FOCUSED_LOG; use --focus to select one")
        return
    for log in focused_logs[:2]:
        gf = log.parent
        candidates = [
            gf / "events.lhe", gf / "events.lhe.gz",
            gf / "events.lhe.rwgt",
        ]
        found = [p for p in candidates if p.is_file()]
        print("GF", gf.relative_to(run))
        print("LHE_CANDIDATES", [(p.name, p.stat().st_size)
                                 for p in found])
        if not found:
            print("LHE_EVENT_INPUT_MISSING")
            continue
        # The reweight program consumes the uncompressed events.lhe.
        inspect_first_event(found[0])



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
    inspect_gf_events(run, focused)

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
