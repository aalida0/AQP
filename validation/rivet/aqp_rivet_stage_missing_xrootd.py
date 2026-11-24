#!/usr/bin/env python3
"""Stage missing fresh Rivet inputs via registered XRootD PFNs, checking catalogue Adler32."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import subprocess
import tempfile
import zlib

ROOT = Path("/data/aalida/AQP_Rivet_full")
OUT = ROOT/"outputs/fresh_rivet_20261124"


def replicas(output, name):
    checksums, pfns = set(), []
    for line in output.splitlines():
        cols = [c.strip() for c in line.split("|")]
        if len(cols) < 7 or cols[1] != "user.aalida" or cols[2] != name:
            continue
        if re.fullmatch(r"[0-9a-fA-F]{8}", cols[4]):
            checksums.add(cols[4].lower())
        match = re.search(r"root://\S+", cols[5])
        if match:
            pfns.append(match.group())
    if len(checksums) != 1 or not pfns:
        raise ValueError("No unambiguous catalogue checksum and XRootD replica")
    return checksums.pop(), sorted(set(pfns), key=lambda p: ("fax.mwt2.org" not in p, p))


def adler(path):
    value = 1
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            value = zlib.adler32(chunk, value)
    return f"{value & 0xffffffff:08x}"


def stage(item):
    sample, name = item
    proc, cfg, _ = sample.split("/")
    dest = ROOT/"inputs"/proc/cfg/name
    try:
        info = subprocess.check_output(
            ["rucio", "list-file-replicas", "user.aalida:"+name],
            text=True, timeout=180)
        expected, pfns = replicas(info, name)
        if dest.exists():
            if adler(dest) != expected:
                raise ValueError("Existing local file has wrong checksum; refusing overwrite")
            print(f"STAGED_OK {name} {expected} existing", flush=True)
            return True
        dest.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".aqp-stage-", dir=dest.parent) as tmp:
            part = Path(tmp)/name
            for pfn in pfns:
                if part.exists():
                    part.unlink()
                try:
                    rc = subprocess.run(["xrdcp", pfn, str(part)],
                                        timeout=900, stdout=subprocess.DEVNULL,
                                        stderr=subprocess.PIPE, text=True)
                except subprocess.TimeoutExpired:
                    print(f"TRANSFER_TIMEOUT {name} {pfn}", flush=True)
                    continue
                # Remote checksum queries can fail AFTER the copy. Only the
                # independent catalogue Adler32 comparison permits publication.
                if part.is_file() and adler(part) == expected:
                    if rc.returncode:
                        print(f"TRANSFER_NONZERO_VERIFIED {name} rc={rc.returncode}", flush=True)
                    part.replace(dest)
                    print(f"STAGED_OK {name} {expected}", flush=True)
                    return True
                print(f"TRANSFER_FAILED {name} {pfn} rc={rc.returncode} {rc.stderr[-500:]}", flush=True)
        raise ValueError("No replica yielded the catalogue checksum")
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"STAGED_FAILED {name} {exc}", flush=True)
        return False


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--limit", type=int, default=0, help="0 means all missing files")
    a = p.parse_args()
    if a.workers < 1 or a.limit < 0:
        p.error("Invalid worker count or limit")
    doc = json.loads((OUT/"production_manifest.json").read_text())
    missing = []
    for sample, data in doc["samples"].items():
        for row in data["included"]:
            name = row["evnt"]
            yoda = OUT/"full"/sample/"yoda"/name.replace(".EVNT.pool.root", ".yoda.gz")
            if yoda.exists() != yoda.with_suffix(".json").exists():
                raise ValueError(f"Incomplete output pair: {yoda}")
            if not yoda.exists():
                missing.append((sample, name))
    print(f"MISSING_EVNT={len(missing)}", flush=True)
    rows = missing[:a.limit] if a.limit else missing
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        ok = sum(pool.map(stage, rows))
    print(f"STAGING_SUMMARY verified={ok} failed={len(rows)-ok}", flush=True)
    return int(ok != len(rows))


if __name__ == "__main__":
    raise SystemExit(main())
