#!/usr/bin/env python3
"""Prepare common finalized YODA objects for native absolute Rivet plotting.

Only BEGIN and Path identifiers are rewritten for the verified electron
alias. All bin values, errors and other annotations are copied unchanged.
The originals remain the authoritative physics YODA files.
"""
import argparse
import gzip
from pathlib import Path

from aqp_vjets_eight_sample_preflight import ANALYSES, SAMPLES, audit
from aqp_vjets_physics_preflight import canonical

ROOT = Path("/data/aalida/AQP_Rivet_full/outputs/Vjets_absolute_plots_20261124")


def common_blocks(source, analyses):
    result = {}
    block = []
    with gzip.open(source, "rt", encoding="utf-8") as f:
        for line in f:
            if line.startswith("BEGIN YODA_"):
                if block:
                    raise ValueError("Nested YODA object in " + str(source))
                block = [line]
            elif block:
                block.append(line)
                if line.startswith("END YODA_"):
                    fields = block[0].rstrip("\n").split(maxsplit=2)
                    if len(fields) != 3:
                        raise ValueError("Missing YODA path in " + str(source))
                    old = fields[2]
                    path = canonical(old)
                    if any(path.startswith("/" + a + "/") for a in analyses):
                        if path in result:
                            raise ValueError("Duplicate canonical path: " + path)
                        # Only identifiers change; all numerical data stay verbatim.
                        annotations = [i for i, s in enumerate(block)
                                       if s.startswith("Path: ")]
                        if len(annotations) != 1 or block[annotations[0]].strip() != "Path: " + old:
                            raise ValueError("Inconsistent YODA Path annotation: " + old)
                        if old != path:
                            block[0] = block[0].replace(old, path, 1)
                            i = annotations[0]
                            block[i] = block[i].replace(old, path, 1)
                        result[path] = "".join(block)
                    block = []
    if block:
        raise ValueError("Truncated YODA object: " + str(source))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", type=Path, default=ROOT)
    a = parser.parse_args()
    _, _, failures = audit()
    if failures:
        return 1
    outdir = a.outdir.expanduser().resolve()
    copies = outdir / "plot_inputs"
    if copies.exists():
        parser.error("Plot-input directory exists; refusing overwrite")
    # Fully validate both process groups before writing any file.
    groups = {}
    for proc, samples in SAMPLES.items():
        objects = {cfg: common_blocks(p, ANALYSES[proc])
                   for cfg, p in samples.items()}
        common = sorted(set.intersection(*(set(v) for v in objects.values())))
        if not common:
            raise ValueError("No common finalized objects for " + proc)
        for name in ANALYSES[proc]:
            if not any(p.startswith("/" + name + "/") for p in common):
                raise ValueError("Missing analysis " + name)
        groups[proc] = (objects, common)
    copies.mkdir(parents=True)
    for proc, (objects, common) in groups.items():
        for cfg, blocks in objects.items():
            dest = copies / f"{proc}_{cfg}.yoda.gz"
            with gzip.open(dest, "wt", encoding="utf-8") as f:
                for path in common:
                    f.write(blocks[path] + "\n")
            # Confirm exact payload preservation on readback.
            if common_blocks(dest, ANALYSES[proc]) != {
                    path: blocks[path] for path in common}:
                raise ValueError("Plot-copy readback mismatch: " + str(dest))
            print(f"PLOT_COPY={dest} OBJECTS={len(common)}")
    print("PLOT_INPUTS=PASS")
    print("PHYSICAL_XSEC_VALIDATED=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
