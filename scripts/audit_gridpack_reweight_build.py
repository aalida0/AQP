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

    print("\n===== WORKER LAUNCHERS AND COMPILED PROGRAMS =====")
    proc = gf.parent if gf.is_dir() else sub
    for p in (proc / "ajob1", gf / "ajob1"):
        if not p.is_file():
            continue
        print("LAUNCHER", p.relative_to(run), "SIZE", p.stat().st_size)
        for n, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
            # No secrets, no arbitrary commands executed: show only
            # lines indicating which generator binary the worker invokes.
            if re.search(r"madevent|mintMC|driver|compile|run_card|event|\.exe|\.x", line, re.I):
                print(f"  L{n}:", line[:240])
                if n > 220:
                    break

    program_candidates = []
    for directory in (proc, gf, sub):
        if not directory.is_dir():
            continue
        for candidate in directory.iterdir():
            if candidate.is_file() and candidate.stat().st_size > 0:
                if candidate.name in ("madevent", "madevent_mintMC", "driver",
                                      "ajob1", "reweight_xsec_events") or (
                        candidate.stat().st_mode & 0o111 and
                        any(token in candidate.name.lower()
                            for token in ("madevent", "mint", "driver"))):
                    program_candidates.append(candidate)
    seen = set()
    elf_files = []
    for p in program_candidates:
        if p in seen:
            continue
        seen.add(p)
        with p.open("rb") as stream:
            magic = stream.read(4)
        if magic != b"\\x7fELF":
            print("NOT_ELF", p.relative_to(run), "BYTES", p.stat().st_size)
            continue
        elf_files.append(p)
        with p.open("rb") as stream:
            data = stream.read(80 * 1024 * 1024)
        print("ELF", p.relative_to(run), "BYTES", p.stat().st_size,
              "HAS_AMCATNLO_LITERAL", b"#aMCatNLO" in data,
              "HAS_WRITE_EVENTS_LITERAL", b"write_events_lhe" in data)
    print("ELF_PROGRAMS_FOUND", len(elf_files))

    log = gf / "log_MINT2.txt"
    print("\n===== EVENT GENERATION WORKER LOG =====")
    if log.is_file():
        patterns = [re.compile(pattern, re.I)
                    for pattern in ("imode", "event", "write", "reweight",
                                    "warning", "error", "run card")]
        show_lines(log, patterns, 55)
    else:
        print("WORKER_LOG_MISSING", log)

    print("\nAUDIT_COMPLETE. The launcher, ELF files and worker log must")
    print("be reconciled with the source before rebuilding anything.")


if __name__ == "__main__":
    main()
