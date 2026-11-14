#!/usr/bin/env python3
"""Incremental Rucio -> local EVNT -> Athena Rivet_i -> per-file YODA pipeline.

Never caps total events or assumes a finished PanDA task. A repeated run adds
newly available EVNT files and skips previously successful file DIDs.
Use from Condor worker nodes for large runs, NOT on AF login nodes.
"""
import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
import zlib
from datetime import datetime, timezone
from pathlib import Path

FILE_RE = re.compile(r"user\.aalida\.\d+\._\d+\.EVNT\.pool\.root")

def cmd(args, cwd=None, env=None, logfile=None):
    if logfile:
        with open(logfile, "w", encoding="utf-8") as out:
            return subprocess.run(args, cwd=cwd, env=env, stdout=out,
                                  stderr=subprocess.STDOUT, check=False).returncode
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True,
                          text=True, check=False)

def listed_files(did):
    p = cmd(["rucio", "list-files", did])
    if p.returncode:
        print(f"SKIP unavailable dataset {did}: {p.stderr.strip()[:180]}", flush=True)
        return []
    files = []
    names = set()
    for line in p.stdout.splitlines():
        m = FILE_RE.search(line)
        if not m or m.group(0) in names:
            continue
        name = m.group(0)
        names.add(name)
        # Rucio list-files reports the event count in the last table column,
        # if that metadata was registered. Do NOT infer it from the task target.
        cols = [s.strip() for s in line.strip().strip("|").split("|")]
        registered_events = int(cols[-1]) if cols and cols[-1].isdigit() else None
        files.append((name, registered_events))
    return files

def read_index(path):
    if not path.exists():
        return set()
    with path.open(newline="", encoding="utf-8") as f:
        return {row["file_did"] for row in csv.DictReader(f) if row.get("file_did")}

def add_index(path, row):
    keys = ["file_did", "dataset_did", "process", "config", "registered_events",
            "yoda", "log", "completed_utc"]
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        if new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in keys})

def process_one(args, process, config, ds, name, expected_events, folder, jo):
    file_did = "user.aalida:" + name
    yodadir = folder / "yoda"
    logsdir = folder / "logs"
    stagedir = folder / "stage"
    for d in (yodadir, logsdir, stagedir):
        d.mkdir(parents=True, exist_ok=True)

    yoda = yodadir / (name.replace(".EVNT.pool.root", "") + ".yoda.gz")
    log = logsdir / (name + ".rivet.log")
    stage = stagedir / name
    index = folder / f"processed_files.shard{args.shard_index:02d}-of-{args.shards:02d}.csv"
    if file_did in read_index(index) and yoda.exists() and yoda.stat().st_size > 100:
        print(f"ALREADY_DONE {file_did}", flush=True)
        return True

    if not stage.is_file() or stage.stat().st_size == 0:
        print(f"DOWNLOAD {file_did}", flush=True)
        p = cmd(["rucio", "download", "--no-subdir", "--dir", str(stagedir), file_did])
        if p.returncode:
            print(f"DOWNLOAD_FAILED {file_did} :: {p.stderr.strip()[:250]}", flush=True)
            return False
    if not stage.exists() or stage.stat().st_size < 100:
        print(f"DOWNLOAD_MISSING {file_did} expected {stage}", flush=True)
        return False

    env = os.environ.copy()
    env.update({
        "AQP_RIVET_INPUT": str(stage.resolve()),
        "AQP_RIVET_OUTPUT": str(yoda.resolve()),
        "AQP_RIVET_ANALYSES": (
            "MC_WJETS,MC_WINC" if process == "Wenu" else "MC_ZJETS,MC_ZINC"
        ),
    })
    print(f"RIVET {file_did}", flush=True)
    # isolate working directory so Athena writes temp files away from output YODA
    workdir = folder / "work" / name
    workdir.mkdir(parents=True, exist_ok=True)
    rc = cmd(["athena.py", str(jo.resolve())], cwd=str(workdir), env=env, logfile=log)
    if rc != 0 or not yoda.is_file() or yoda.stat().st_size <= 100:
        print(f"RIVET_FAILED {file_did} exit={rc}; inspect {log}", flush=True)
        if yoda.exists():
            yoda.unlink()
        return False
    add_index(index, {
        "file_did": file_did, "dataset_did": ds, "process": process,
        "config": config, "registered_events": expected_events or "",
        "yoda": str(yoda), "log": str(log),
        "completed_utc": datetime.now(timezone.utc).isoformat(),
    })
    if not args.keep_evnt:
        stage.unlink()
    if not args.keep_work:
        shutil.rmtree(workdir)
    print(f"DONE {file_did}: {yoda}", flush=True)
    return True

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True, help="Large /data storage")
    p.add_argument("--job-options", type=Path, required=True)
    p.add_argument("--process", choices=["Zee", "Wenu", "all"], default="all")
    p.add_argument("--config", choices=["standard111", "delta111", "delta221", "delta441", "all"], default="all")
    p.add_argument("--versions", default="v2,v3",
                   help="Comma-separated task versions to discover, default v2,v3; NO event limit")
    p.add_argument("--max-files", type=int, default=0,
                   help="Optional diagnostic file cap per configuration, 0=ALL currently available")
    p.add_argument("--shards", type=int, default=1, help="Parallel workers per configuration")
    p.add_argument("--shard-index", type=int, default=0, help="This worker index, zero based")
    p.add_argument("--discover-only", action="store_true")
    p.add_argument("--merge-only", action="store_true")
    p.add_argument("--keep-evnt", action="store_true", help="Keep large EVNT files after Rivet")
    p.add_argument("--keep-work", action="store_true", help="Keep Athena working directories")
    a = p.parse_args()
    if a.max_files < 0:
        p.error("--max-files must be >=0")
    if a.shards < 1 or not (0 <= a.shard_index < a.shards):
        p.error("require --shards >= 1 and 0 <= --shard-index < --shards")
    root = a.root.expanduser().resolve()
    jo = a.job_options.expanduser().resolve()
    if not a.discover_only and not a.merge_only:
        if not jo.is_file():
            p.error(f"missing Athena JO: {jo}")
        for executable in ("rucio", "athena.py"):
            if shutil.which(executable) is None:
                p.error(f"{executable} not on PATH; configure ATLAS environment")
    if a.merge_only and not shutil.which("rivet-merge"):
        p.error("rivet-merge not on PATH; configure a Rivet environment")
    if a.discover_only and not shutil.which("rucio"):
        p.error("rucio not on PATH")

    processes = ["Zee", "Wenu"] if a.process == "all" else [a.process]
    configs = ["standard111", "delta111", "delta221", "delta441"] if a.config == "all" else [a.config]
    failed = 0
    for proc in processes:
        for cfg in configs:
            folder = root / proc / cfg
            if a.merge_only:
                # Version-separated merging: do not combine v2 and v3
                # without checking weight and phase-space equivalence.
                indexes = sorted(folder.glob("processed_files*.csv"))
                if not indexes:
                    print(f"NO_YODA {proc} {cfg}", flush=True)
                    continue
                rows = []
                for index in indexes:
                    with index.open(newline="", encoding="utf-8") as fh:
                        rows.extend(csv.DictReader(fh))
                mergedir = folder / "merged"
                mergedir.mkdir(parents=True, exist_ok=True)
                for ver in (v.strip() for v in a.versions.split(",") if v.strip()):
                    paths = sorted({
                        Path(row["yoda"]) for row in rows
                        if f".{ver}_EVNT.pool.root" in row.get("dataset_did", "")
                        and row.get("yoda") and Path(row["yoda"]).is_file()
                    })
                    if not paths:
                        print(f"NO_YODA {proc} {cfg} {ver}", flush=True)
                        continue
                    out = mergedir / f"{proc}_{cfg}_{ver}_nominal_shapes.yoda.gz"
                    print(f"MERGING {proc} {cfg} {ver}: {len(paths)} YODA files", flush=True)
                    rc = cmd(["rivet-merge", "-e", "-o", str(out)] +
                             [str(src) for src in paths], logfile=mergedir / f"merge_{ver}.log")
                    if rc:
                        failed += 1
                        print(f"MERGE_FAILED: see {mergedir / ('merge_' + ver + '.log')}", flush=True)
                    else:
                        print(f"MERGED {out}", flush=True)
                continue

            entries = {}
            for ver in (v.strip() for v in a.versions.split(",") if v.strip()):
                ds = f"user.aalida:user.aalida.AQP.{proc}.{cfg}.FxFx2M.{ver}_EVNT.pool.root"
                for name, event_count in listed_files(ds):
                    # If a file is in more than one dataset, process it only once.
                    entries.setdefault(name, (ds, event_count))
            print(f"{proc} {cfg}: {len(entries)} currently registered EVNT files", flush=True)
            if a.discover_only:
                continue
            index = folder / f"processed_files.shard{a.shard_index:02d}-of-{a.shards:02d}.csv"
            done = read_index(index)
            # Stable CRC32 partition: no two shards choose the same LFN.
            new = [(name, ds, n) for name, (ds, n) in sorted(entries.items())
                   if zlib.crc32(name.encode("utf-8")) % a.shards == a.shard_index
                   and ("user.aalida:" + name not in done
                        or not (folder / "yoda" /
                                (name.replace(".EVNT.pool.root", "") + ".yoda.gz")).is_file())]
            if a.max_files:
                new = new[:a.max_files]
            print(f"{proc} {cfg}: {len(done)} previously done; {len(new)} new selected", flush=True)
            for name, ds, n in new:
                if not process_one(a, proc, cfg, ds, name, n, folder, jo):
                    failed += 1
    if failed:
        print(f"FAILED_UNITS={failed}", flush=True)
        return 1
    print("INCREMENTAL_PASS_COMPLETE — run again when more EVNT files finish", flush=True)
    return 0

if __name__ == "__main__":
    sys.exit(main())
