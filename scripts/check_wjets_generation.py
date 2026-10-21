#!/usr/bin/env python3
"""Read-only AQP W+jets MINT2/LHE checks (Python 3.8+).

Checks allocation, archived per-GF MINT2 logs, combined gzip LHE event count,
and MINT1 res_1.dat files. Does not modify production files or unpickle.
"""
import argparse
import gzip
import re
from pathlib import Path

CONFIGS = ("standard111", "delta111", "delta221", "delta441_backup")
EVENT = re.compile(r"^\s*<event(?:\s|>)")
IMODE2 = re.compile(r"\bimode is\s+2\b")


def count_events(path):
    count = 0
    with gzip.open(str(path), "rt", encoding="utf-8", errors="replace") as source:
        for line in source:
            if EVENT.match(line):
                count += 1
    return count


def inspect(base, cfg):
    print("\n========== %s ==========" % cfg)
    process = base / cfg / "PROCNLO_loop_sm-no_b_mass_0"
    sub = process / "SubProcesses"
    if not sub.is_dir():
        print("Missing:", sub)
        return
    gfdirs = [p for p in sub.glob("P*/GF*") if p.is_dir()]
    finished = sum(1 for p in gfdirs
                   if (p / "res_1.dat").is_file()
                   and (p / "res_1.dat").stat().st_size > 0)
    print("GF targets / nonempty res_1.dat: %d / %d" % (len(gfdirs), finished))
    for filename in ("job_status.pkl", "nevents_unweighted", "orderstags_glob.dat"):
        path = sub / filename
        print("%s: %s" % (filename, "present" if path.is_file() and path.stat().st_size else "ABSENT"))
    allocations = sub / "nevents_unweighted"
    allocated = None
    if allocations.is_file() and allocations.stat().st_size:
        allocated = 0
        active = []
        entries = 0
        bad = 0
        for line in allocations.read_text(errors="replace").splitlines():
            if not line.strip():
                continue
            entries += 1
            parts = line.split()
            try:
                n = int(parts[1])
                gfrel = Path(parts[0]).parent
            except (ValueError, IndexError):
                bad += 1
                continue
            if n > 0:
                allocated += n
                active.append((str(gfrel), n))
        print("Allocation: %d active / %d entries; %d events; malformed=%d" %
              (len(active), entries, allocated, bad))
        missing_archive = []
        abnormal_archive = []
        normal_archive = 0
        fallback_working = 0
        for gfrel, n in active:
            folder = sub / gfrel
            archived = folder / "log_MINT2.txt"
            working = folder / "log.txt"
            content = (archived.read_text(errors="replace")
                       if archived.is_file() else "")
            if not IMODE2.search(content):
                missing_archive.append((gfrel, n))
                if working.is_file() and IMODE2.search(
                        working.read_text(errors="replace")):
                    fallback_working += 1
            elif "Time spent in Total" not in content or "Fortran runtime error" in content:
                abnormal_archive.append((gfrel, n))
            else:
                normal_archive += 1
        print("Normal archived MINT2 logs: %d" % normal_archive)
        print("Allocated GF without usable archived MINT2 log: %d" %
              len(missing_archive))
        print("Allocated GF with abnormal archived MINT2 log: %d" %
              len(abnormal_archive))
        print("Missing archived logs with imode2 in working log.txt: %d" %
              fallback_working)
        for title, rows in (("NO_ARCHIVED_MINT2", missing_archive),
                            ("ABNORMAL_ARCHIVED_MINT2", abnormal_archive)):
            for gfrel, n in rows[:20]:
                print("  %s: %s (allocation %d)" % (title, gfrel, n))
            if len(rows) > 20:
                print("  ... %d more" % (len(rows) - 20))
    else:
        print("No allocation metadata; requires recovery before generation.")
    lhe = process / "Events" / "run_01" / "events.lhe.gz"
    if lhe.is_file() and lhe.stat().st_size:
        try:
            events = count_events(lhe)
            print("Combined LHE: gzip readable; %d <event> blocks" % events)
            if allocated is not None:
                print("LHE count vs allocation: %s" %
                      ("MATCH" if events == allocated else "DIFFERENT"))
        except (OSError, EOFError, UnicodeError) as err:
            print("Combined LHE cannot be fully read:", err)
    else:
        print("Combined LHE: absent")
    print("These structural checks are not full physics/gridpack validation.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=str(Path.home() / "AQP/Wjets/WENU"))
    args = parser.parse_args()
    for cfg in CONFIGS:
        inspect(Path(args.base).expanduser(), cfg)


if __name__ == "__main__":
    main()
