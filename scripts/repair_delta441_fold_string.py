#!/usr/bin/env python3
"""Repair ONLY the absent fold_string key in a trusted local Δ441 checkpoint.

Run the script from /home. All modified files and backup live under /data.
The existing MINT1 res_1.dat, grids, run cards and original HOME tree are
never changed. Default mode is read-only; use --apply for the atomic repair.

WARNING: This script unpickles a user-owned checkpoint. Never give it a
pickle from an untrusted source.
"""
import argparse
import hashlib
import os
import pickle
import re
import sys
import tempfile
from pathlib import Path

EXPECTED_PROCESS = "PROCNLO_loop_sm-no_b_mass_0"
EXPECTED_FOLDING = [4, 4, 1]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as src:
        for block in iter(lambda: src.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def effective_card_value(card, field):
    value = None
    for line in card.read_text(errors="replace").splitlines():
        line = line.split("#", 1)[0].split("!", 1)[0]
        if "=" not in line:
            continue
        raw, key = line.rsplit("=", 1)
        if key.strip().lower() == field:
            value = raw.strip().lower()
    return value


def run(args):
    process = Path(args.process).expanduser().resolve(strict=True)
    if not process.is_dir() or process.name != EXPECTED_PROCESS:
        raise ValueError("Expected existing PROCNLO_loop_sm-no_b_mass_0 process")
    if not str(process).startswith("/data/aalida/AQP/Wjets/WENU/delta441_backup/"):
        raise ValueError("Only the /data/aalida/.../delta441_backup process is permitted")

    run_card = process / "Cards" / "run_card.dat"
    if not run_card.is_file():
        raise ValueError("Missing run card")
    fold_value = effective_card_value(run_card, "folding")
    try:
        folding = [int(x) for x in re.split(r"[\s,]+", fold_value) if x]
    except (TypeError, ValueError) as exc:
        raise ValueError("Cannot parse folding {!r}".format(fold_value)) from exc
    if folding != EXPECTED_FOLDING:
        raise ValueError("Expected Δ441 folding; run card has {}".format(folding))
    delta = effective_card_value(run_card, "mcatnlo_delta")
    if delta not in ("true", ".true."):
        raise ValueError("Expected MC@NLO-Delta enabled; effective value {!r}".format(delta))

    status = process / "SubProcesses" / "job_status.pkl"
    backup = status.with_name("job_status.pre_fold_string.pkl")
    if not status.is_file() or status.is_symlink():
        raise ValueError("Missing checkpoint or symlink: {}".format(status))
    with status.open("rb") as stream:
        jobs = pickle.load(stream)
    if not isinstance(jobs, list) or len(jobs) != 300:
        raise ValueError("Expected exactly 300 job dictionaries")
    if not all(isinstance(job, dict) for job in jobs):
        raise ValueError("Non-dictionary job")
    needed = {"p_dir", "channel", "dirname", "run_mode",
              "mint_mode", "errorABS", "resultABS"}
    seen = set()
    existing_fold = 0
    for job in jobs:
        if not needed.issubset(job):
            raise ValueError("Job missing required MG fields")
        gf = "GF" + str(job["channel"])
        expected = process / "SubProcesses" / str(job["p_dir"]) / gf
        real_path = Path(str(job["dirname"])).resolve(strict=True)
        if real_path != expected.resolve(strict=True):
            raise ValueError("Job GF path differs: {!r}".format(job["dirname"]))
        key = (job["p_dir"], job["channel"])
        if key in seen:
            raise ValueError("Duplicate GF channel {}".format(key))
        seen.add(key)
        if job["run_mode"] != "all" or job["mint_mode"] != 2:
            raise ValueError("Unexpected stage/mode at GF {}".format(key))
        if "fold_string" in job:
            existing_fold += 1
            if job["fold_string"] != "4 4 1":
                raise ValueError("Wrong fold_string value at GF {}".format(key))
    if existing_fold not in (0, 300):
        raise ValueError("Only a fraction of the GF jobs has fold_string")
    print("DELTA441_FOLD_STRING_AUDIT_PASS")
    print("Process:", process)
    print("Jobs:", len(jobs))
    print("Effective folding:", fold_value, "=>", "4 4 1")
    print("Effective MC@NLO-Delta:", delta)
    print("Jobs already having fold_string:", existing_fold)
    print("Original checkpoint SHA256:", sha256(status))

    if existing_fold == len(jobs):
        print("ALREADY_REPAIRED: no changes needed")
        return 0
    if not args.apply:
        print("DRY_RUN_ONLY: rerun with --apply to back up and repair job_status.pkl")
        return 0
    if backup.exists() or backup.is_symlink():
        raise ValueError("Backup already exists; refusing to overwrite: {}".format(backup))
    for job in jobs:
        job["fold_string"] = "4 4 1"
    # Preserve the original inode at a new /data name, without moving it.
    os.link(status, backup)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=status.parent, prefix=".job_status_fold_string_",
            delete=False
        ) as out:
            temporary = Path(out.name)
            pickle.dump(jobs, out, protocol=2)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, status)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print("BACKUP_CREATED:", backup)
    print("CHECKPOINT_REPAIRED:", status)
    print("Repaired checkpoint SHA256:", sha256(status))
    print("Preserved original SHA256:", sha256(backup))
    print("No MadGraph executable or MINT integration was run.")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--process", required=True, help="Absolute /data delta441_backup process path")
    parser.add_argument("--apply", action="store_true",
                        help="Write backup and atomically repair checkpoint")
    args = parser.parse_args()
    try:
        return run(args)
    except (OSError, ValueError, pickle.UnpicklingError) as error:
        print("DELTA441_FOLD_STRING_FAILED:", error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
