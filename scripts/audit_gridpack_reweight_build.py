#!/usr/bin/env python3
"""Read-only audit of compiled NLO LHE-reweight support in an extracted gridpack.

No recompilation, no gridpack edits, and no deletion. This checks why
store_rwgt_info=True in the run card still yields LHE events with no #aMCatNLO.
"""
import argparse
from pathlib import Path
import re


def show_lines(path, expressions, limit=12):
    lines = path.read_text(errors="replace").splitlines()
    selected = [
        (i, line.strip()[:200])
        for i, line in enumerate(lines, 1)
        if any(pattern.search(line) for pattern in expressions)
    ]
    for number, line in selected[:limit]:
        print(f"    L{number}: {line}")
    print("    MATCHES", len(selected))
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path, help="Failed ~/gridpack-validation/zee1jet.* directory")
    parser.add_argument("--focus", default="P1_gd_demep/GF4.0")
    args = parser.parse_args()
    run = args.run.expanduser().resolve(strict=True)
    madevent = run / "madevent"
    sub = madevent / "SubProcesses"
    if not sub.is_dir():
        parser.error("No madevent/SubProcesses tree found")
    print("RUN", run)
    print("AUDIT_ONLY: no writes, recompilation, or deletion")

    for card in [madevent / "Cards" / "run_card.dat",
                 madevent / "Cards" / "me5_configuration.txt"]:
        print("\nCARD", card.relative_to(run), "PRESENT", card.is_file())
        if card.is_file():
            show_lines(card, [re.compile(r"\b(?:store_rwgt_info|reweight_scale|reweight_pdf|systematics_program)\b",
                                         re.I)], 15)

    names = ("madfks_mcatnlo.inc", "driver_mintMC.f", "write_event.f",
             "handling_lhe_events.f", "analysis_lhe.f")
    expressions = [
        re.compile(x, re.I)
        for x in ("AddInfoLHE", "doreweight", "store_rwgt_info",
                  "write_events_lhe", "#aMCatNLO", "parameter.*AddInfoLHE")
    ]
    print("\n===== FORTRAN SOURCE AUDIT =====")
    for name in names:
        # Include both process-local and top-level templates. Globbing
        # only named sources avoids walking large event-file collections.
        candidates = [sub / name, madevent / "Source" / name]
        candidates += sorted(sub.glob("P*/" + name))[:4]
        present = [p for p in candidates if p.is_file()]
        if not present:
            print("SOURCE_MISSING", name)
        for p in present[:5]:
            print("SOURCE", p.relative_to(run), "BYTES", p.stat().st_size)
            show_lines(p, expressions, 14)

    print("\n===== FOCUSED GF WORKER ARTIFACTS =====")
    gf = sub / args.focus
    if not gf.is_dir():
        print("FOCUS_MISSING", gf)
    else:
        print("GF", gf.relative_to(run))
        for card in (gf / "run_card.dat", gf.parent / "run_card.dat",
                     sub / "run_card.dat"):
            print("WORKER_CARD", card.relative_to(run), "PRESENT", card.is_file())
            if card.is_file():
                show_lines(card, [
                    re.compile(r"store_rwgt_info|reweight_scale|reweight_pdf",
                               re.I)], 12)
        for p in sorted(gf.iterdir()):
            if p.is_file() and (p.name in (
                    "events.lhe", "reweight_xsec_events.output",
                    "log_MINT2.txt", "log_MINT1.txt", "ajob1",
                    "madevent", "driver", "reweight_xsec_events",
                    "run_card.dat") or p.suffix in (".exe", ".out")):
                print("  FILE", p.name, "BYTES", p.stat().st_size,
                      "MTIME_NS", p.stat().st_mtime_ns)

    # A compiled binary *may* contain the literal marker; its presence
    # is informative, but its absence alone does not prove a code defect.
    print("\n===== COMPILED WORKER CODE MARKER CHECK =====")
    found = []
    proc = gf.parent if gf.is_dir() else sub
    for p in [gf / "ajob1", proc / "ajob1", proc / "madevent",
              gf / "madevent", gf / "driver", proc / "driver"]:
        if p.is_file() and p.stat().st_size > 0:
            found.append(p)
            with p.open("rb") as stream:
                # Limit read to avoid loading unusually large binaries.
                data = stream.read(100 * 1024 * 1024)
            print("BINARY", p.relative_to(run), "SIZE", p.stat().st_size,
                  "HAS_AMCATNLO_LITERAL", b"#aMCatNLO" in data,
                  "HAS_WRITE_EVENTS_LITERAL", b"write_events_lhe" in data)
    if not found:
        print("NO_FOCUSED_WORKER_EXECUTABLE_FOUND")
    print("\nAUDIT_COMPLETE. Source declarations and the effective run card must")
    print("be reconciled before rebuilding workers or changing gridpack provenance.")


if __name__ == "__main__":
    main()
