#!/usr/bin/env python3
"""Smoke recovery: run ATLAS arrange_output on a copied 20-event LHE.

No Condor submissions, NLO integration, or modifications of the source.
Requires asetup 23.6.63,AthGeneration on the AF.
"""
from pathlib import Path
from types import SimpleNamespace
import gzip
import os
import re
import shutil
import tarfile
import tempfile

from MadGraphControl.MadGraphUtils import arrange_output, get_expected_systematic_names

assert get_expected_systematic_names({}) == [], "Nominal-only output override not supported"

root = Path.home() / "AQP/condor-smoke"
src = root / "MG1jet-v3nosyst.LTC55Y/PROCNLO_loop_sm-no_b_mass_0/Events/run_01"
plain = src / "events.lhe"
compressed = src / "events.lhe.gz"
assert plain.is_file() or compressed.is_file(), f"No generated LHE in {src}"

stage = Path(tempfile.mkdtemp(prefix="MG1jet-v3-arrange.", dir=root))
proc = stage / "isolated_process"
events = proc / "Events/run_01"
events.mkdir(parents=True)
(proc / "Cards").mkdir()
out_input = events / "events.lhe.gz"

if compressed.is_file():
    shutil.copy2(compressed, out_input)
else:
    with plain.open("rb") as reader, gzip.open(out_input, "wb") as writer:
        shutil.copyfileobj(reader, writer)

with gzip.open(out_input, "rt", errors="replace") as reader:
    count = sum(bool(re.match(r"\s*<event(?:\s[^>]*)?>\s*$", line)) for line in reader)
assert count == 20, f"Expected 20 input events, found {count}"

os.chdir(stage)
run_args = SimpleNamespace(outputTXTFile="smoke_lhe_events.tar.gz")
arrange_output(process_dir=str(proc), runArgs=run_args, lhe_version=3,
               saveProcDir=True, pdf_setting={})

archive_path = stage / "smoke_lhe_events.tar.gz"
assert archive_path.is_file() and archive_path.stat().st_size > 0
with tarfile.open(archive_path, "r:gz") as archive:
    members = [x for x in archive.getmembers()
               if x.isfile() and x.name.endswith(".events")]
    assert len(members) == 1, f"Unexpected contents: {archive.getnames()}"
    contents = archive.extractfile(members[0]).read().decode(errors="replace")
assert contents.rstrip().endswith("</LesHouchesEvents>")
assert len(re.findall(r"(?m)^\s*<event(?:\s[^>]*)?>\s*$", contents)) == 20
assert len(re.findall(r"(?m)^\s*</event>\s*$", contents)) == 20
print("V3_NOMINAL_ONLY_ARRANGE_PASS 20 events")
print("RECOVERED_ATLAS_LHE_ARCHIVE", archive_path)
print("NO_CONDOR_OR_INTEGRATION_PERFORMED")
