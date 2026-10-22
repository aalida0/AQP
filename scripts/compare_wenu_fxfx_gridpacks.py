#!/usr/bin/env python3
"""Read-only comparison of Wenu FxFx NLO gridpack metadata.

Usage: python3 compare_wenu_fxfx_gridpacks.py /data/aalida/AQP/Wjets/WENU/gridpacks
Archives are streamed (one gzip decompression pass each). No files are
unpacked or altered. For multi-GB archives, use a worker, not a login node.
"""
from pathlib import Path
import argparse
import re
import tarfile

TARGETS = {
    "run_card.dat": "Cards/run_card.dat",
    "make_opts": "Source/make_opts",
    "amcatnlo_configuration.txt": "Cards/amcatnlo_configuration.txt",
    "SubProcesses/makefile": "SubProcesses/makefile",
}
WANT = (
    "folding", "mcatnlo_delta", "ickkw", "lhaid", "pdlabel",
    "event_norm", "ptj", "jetradius", "nevents", "parton_shower",
    "run_mode", "nb_core", "LDFLAGS", "STDLIB", "LINKLIBS",
)

def keep_line(line: str, kind: str) -> bool:
    line = line.strip()
    if not line or line.startswith("#"):
        return False
    words = WANT[:10] if kind == "run_card.dat" else WANT[10:]
    return any(re.search(r"\b" + re.escape(w) + r"\b", line, re.I)
               for w in words) or (kind == "make_opts" and "-lc++" in line)

def scan_one(path: Path) -> None:
    print("\n" + "=" * 70)
    print(path.name)
    print("compressed bytes:", path.stat().st_size)
    data = {}
    top_debug = []
    checkpoints = 0
    with tarfile.open(path, mode="r|gz") as tar:
        for member in tar:
            if not member.isfile():
                continue
            name = member.name.lstrip("./")
            if name.endswith("SubProcesses/job_status.pkl"):
                checkpoints += 1
                print("checkpoint:", name, "size:", member.size)
            if name.endswith("_debug.log") and "/SubProcesses/" not in name:
                top_debug.append(name)
            for kind, suffix in TARGETS.items():
                if name.endswith(suffix) and kind not in data:
                    if member.size > 1_000_000:
                        data[kind] = ["(text file too large)"]
                        break
                    stream = tar.extractfile(member)
                    if stream:
                        txt = stream.read().decode("utf-8", "replace")
                        data[kind] = [x.strip()[:240] for x in txt.splitlines()
                                      if keep_line(x, kind)]
                    break
    for kind in TARGETS:
        print("\n[" + kind + "]")
        for line in data.get(kind, ["NOT FOUND"]):
            print(" ", line)
    print("\ncheckpoints:", checkpoints)
    print("top-level historical debug logs:", len(top_debug))
    for line in top_debug[:12]:
        print(" ", line)
    print("Reminder: the Pythia8 dummy/FxFx settings live in the JobOption/transform.")

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("gridpack_dir", type=Path)
    ap.add_argument("--pattern", default="*Wenu*GRID.tar.gz")
    a = ap.parse_args()
    files = sorted(a.gridpack_dir.glob(a.pattern))
    if not files:
        ap.error("No matching Wenu gridpack archives found")
    print("Read-only archive comparison:", len(files), "gridpacks")
    for file in files:
        scan_one(file)

if __name__ == "__main__":
    main()
