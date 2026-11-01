#!/usr/bin/env python3
"""Static scaffold checks only: never imports Athena or starts Condor."""
import argparse
import json
from pathlib import Path


def check(sample: Path) -> None:
    sample = sample.resolve(strict=True)
    data = json.loads((sample / "sample.json").read_text())
    if sample.name != data["dsid"]:
        raise ValueError("Directory DSID disagrees with sample.json")
    if sample.parent.name != data["process"]:
        raise ValueError("Directory process disagrees with sample.json")
    if data["status"] != "scaffold_only_not_for_production":
        raise ValueError("Checker validates only scaffolds")
    joboptions = list(sample.glob("mc.*.py.template"))
    if len(joboptions) != 1:
        raise ValueError("Expected exactly one JO template")
    jo = joboptions[0].read_text()
    compile(jo, str(joboptions[0]), "exec")
    if "AQP" in jo:
        raise ValueError("Keep project names out of the JO")
    for item in ("is_gen_from_gridpack()", "MADGRAPH_PDFSETTING",
                 "get_files", "grid_pack=BUILD_GRIDPACK",
                 "fxfx_exclusive_kt.patch", "delta_tolerance.patch",
                 "FOLDING", "USE_DELTA"):
        if item not in jo:
            raise ValueError("Missing stage or patch hook: " + item)
    fxfx = sample / "fxfx_exclusive_kt.patch"
    if not fxfx.is_file():
        raise ValueError("Missing colocated FxFx patch")
    patch = fxfx.read_text()
    if "SubProcesses/cuts.f" not in patch or "amcatnlo_fastjetdmergemax" not in patch:
        raise ValueError("FxFx patch differs from expected PR #426 shape")
    print("SCAFFOLD_STATIC_PASS", sample)
    print("NOT_PRODUCTION_READY: Delta/Condor and Grid validation remain")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sample", type=Path)
    check(parser.parse_args().sample)
