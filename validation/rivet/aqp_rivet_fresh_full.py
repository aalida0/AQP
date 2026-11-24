#!/usr/bin/env python3
"""Freeze EVNT/log pairs and process the full fresh Rivet campaign in shards."""
import argparse
import json
import math
from pathlib import Path
import tarfile

from aqp_rivet_fresh_pilot import ROOT, LOGS, TASKS, ROUTINES, production_did, process_file
from aqp_rivet_stream import listed_files
from aqp_vjets_generator_xsec_evidence import decode_log, log_paths
from aqp_vjets_v2_xsec_match import extract_xsec, job_key
from aqp_vjets_physics_preflight import scan_yoda
from aqp_vjets_xsec_per_file import get_first

OUT = ROOT/"outputs/fresh_rivet_20261124"
MANIFEST = OUT/"production_manifest.json"
COUNTS = (398, 391, 378, 1972, 399, 393, 379, 1984)
SHARDS = 32


def prepare():
    samples = {}
    blocked = False
    for (proc, cfg, ver), expected in zip(TASKS, COUNTS):
        sample = f"{proc}/{cfg}/{ver}"
        ds = production_did(proc, cfg, ver)
        task = TASKS[(proc, cfg, ver)]
        entries = sorted(listed_files(ds))
        if len(entries) != expected or any(
                job_key(name) is None or job_key(name)[0] != task for name, _ in entries):
            raise ValueError(f"{sample}: expected {expected} EVNTs from {task}, got {len(entries)}")
        by_id = {}
        for path in log_paths(LOGS/proc/cfg/ver):
            key = job_key(path)
            if key and key[0] == task:
                by_id.setdefault(key, []).append(path)
        included, excluded = [], []
        seen = set()
        for name, registered in entries:
            key = job_key(name)
            if key in seen:
                raise ValueError(f"Duplicate EVNT job {key}")
            seen.add(key)
            paths = by_id.get(key, [])
            issue = None
            if len(paths) != 1:
                issue = "MISSING_LOG" if not paths else "DUPLICATE_LOG"
            else:
                try:
                    info, issue = extract_xsec(decode_log(paths[0]))
                except (OSError, ValueError, EOFError, tarfile.TarError) as exc:
                    issue = str(exc)
            if issue:
                excluded.append({"evnt": name, "reason": issue})
                print(f"EXCLUDED {sample} {name} {issue}")
                continue
            n = 1000 if cfg == "delta441" else 5000
            if registered is not None and registered != n:
                raise ValueError(f"{name}: unexpected registered event count {registered}")
            included.append({"evnt": name, "entries": n, "log": str(paths[0]), "xs": info})
        # One missing Wenu D441 log was accepted by the user. The two known
        # invalid-XSEC jobs can be excluded only if their own logs fail validation.
        allowed = (proc, cfg, ver) == ("Wenu", "delta441", "v3")
        known_bad = {1393, 1701}
        extra = [r for r in excluded if job_key(r["evnt"])[1] not in known_bad]
        if excluded and (not allowed or len(extra) > 1 or
                         any(r["reason"] != "MISSING_LOG" for r in extra)):
            blocked = True
        samples[sample] = {"dataset": ds, "included": included, "excluded": excluded}
        print(f"MANIFEST {sample}: {len(included)}/{expected} paired; excluded={len(excluded)}")
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT/"production_manifest_candidate.json"
    target.write_text(json.dumps({"samples": samples, "shards": SHARDS}, indent=2)+"\n")
    if blocked:
        raise ValueError(f"Unexpected exclusions: review {target} before submission")
    if MANIFEST.exists():
        if json.loads(MANIFEST.read_text()) != json.loads(target.read_text()):
            raise ValueError("Existing frozen manifest differs; refusing to replace it")
    else:
        with MANIFEST.open("x") as f:
            f.write(target.read_text())
    print(f"MANIFEST_READY={MANIFEST}")


def run_shard(sample, shard):
    doc = json.loads(MANIFEST.read_text())
    if doc["shards"] != SHARDS or not 0 <= shard < SHARDS:
        raise ValueError("Invalid shard")
    proc, cfg, ver = sample.split("/")
    data = doc["samples"][sample]
    out = OUT/"full"/proc/cfg/ver/"yoda"
    rows = data["included"][shard::SHARDS]
    print(f"SHARD={sample} {shard}/{SHARDS} FILES={len(rows)}", flush=True)
    failed = 0
    for r in rows:
        dest = out/(r["evnt"].removesuffix(".EVNT.pool.root")+".yoda.gz")
        receipt = dest.with_suffix(".json")
        try:
            if dest.exists() or receipt.exists():
                prev = json.loads(receipt.read_text())
                meta = scan_yoda(dest)
                if (meta["error"] or prev["evnt"] != r["evnt"] or
                        prev["entries"] != r["entries"] or
                        not math.isclose(get_first(meta, "_XSEC"), r["xs"]["xs_pb"], rel_tol=1e-4)
                        or any(not meta["analyses"].get(a.split(":")[0]) for a in ROUTINES[proc])):
                    raise ValueError("Existing output inconsistent; do not overwrite")
                print(f"ALREADY_DONE={dest}", flush=True)
                continue
            process_file(proc, cfg, ver, data["dataset"], r["evnt"], r["entries"],
                         Path(r["log"]), r["xs"], out)
        except Exception as exc:
            failed += 1
            print(f"FRESH_FAILED={r['evnt']} {type(exc).__name__}: {exc}", flush=True)
    print(f"SHARD_DONE={sample} {shard} FAILED={failed}", flush=True)
    return int(failed != 0)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prepare", action="store_true")
    p.add_argument("--sample", choices=["/".join(s) for s in TASKS])
    p.add_argument("--shard", type=int)
    a = p.parse_args()
    if a.prepare:
        prepare()
        return 0
    if a.sample is None or a.shard is None:
        p.error("Use --prepare or --sample and --shard")
    return run_shard(a.sample, a.shard)


if __name__ == "__main__":
    raise SystemExit(main())
