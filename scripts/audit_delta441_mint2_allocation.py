#!/usr/bin/env python3
"""Read-only Δ441 MINT2 event-allocation plan from MG5_aMC@NLO v3.5.11.

Run this Python script from /home, with --process under /data.
Only reads user-trusted, locally generated job_status.pkl and run_card.
No MadGraph execution, no process modifications, and no event generation.

Source:
  madgraph/interface/amcatnlo_run_interface.py v3.5.11:
  update_random_seed() 1878-1888
  create_jobs_to_run() 2124-2147
  update_jobs_to_run() 2672-2707
  check_the_need_to_split() 2573-2612

WARNING: pickle.load must only be used with your own trusted checkpoints.
"""
import argparse
import math
import pickle
import random
import re
import sys
from pathlib import Path


def effective_run_card(card):
    vals = {}
    for line in card.read_text(errors="replace").splitlines():
        line = line.split("#", 1)[0].split("!", 1)[0]
        if "=" not in line:
            continue
        val, key = line.rsplit("=", 1)
        vals[key.strip().lower()] = val.strip()
    return vals


def check_jobs(proc, jobs):
    if not isinstance(jobs, list) or len(jobs) != 300:
        raise ValueError("Expected 300 jobs in locally reconstructed checkpoint")
    seen = set()
    last_error = float("inf")
    for job in jobs:
        if not isinstance(job, dict) or not {
            "p_dir", "channel", "dirname", "split", "run_mode",
            "fold_string", "resultABS", "result", "errorABS",
            "wgt_frac", "mint_mode",
        }.issubset(job):
            raise ValueError("Malformed checkpoint dictionary")
        rel = (str(job["p_dir"]), str(job["channel"]))
        if rel in seen:
            raise ValueError("Repeated GF job: {}".format(rel))
        seen.add(rel)
        expected = proc / "SubProcesses" / rel[0] / ("GF" + rel[1])
        given = Path(str(job["dirname"]))
        if given != expected or not (expected / "res_1.dat").is_file():
            raise ValueError("Incorrect GF path or missing MINT1 result: {}".format(given))
        if job["fold_string"] != "4 4 1" or job["run_mode"] != "all" or job["split"] != 0:
            raise ValueError("Incorrect job metadata in {}".format(given))
        absolute = float(job["resultABS"])
        if not math.isfinite(absolute) or absolute <= 0:
            raise ValueError("Nonpositive/nonfinite ABS contribution in {}".format(given))
        error = float(job["errorABS"])
        if error > last_error:
            raise ValueError("GF jobs not ordered by descending absolute error")
        last_error = error


def get_seed(proc, vals):
    randfile = proc / "SubProcesses" / "randinit"
    seed_text = randfile.read_text().strip()
    if not re.fullmatch(r"r=\d+", seed_text):
        raise ValueError("Unexpected seed file: {}".format(seed_text))
    initial_seed = int(seed_text[2:])
    iseed = int(vals.get("iseed", "0"))
    # From MG update_random_seed(): iseed=0 advances prior randinit.
    if iseed == 0:
        next_seed = initial_seed + 1
    else:
        next_seed = iseed
    return initial_seed, iseed, next_seed


def allocate(jobs, seed, nevents):
    # Exactly mirrors update_jobs_to_run(step=1, fixed_order=False)
    # in MG5_aMC@NLO v3.5.11 for unsplit jobs.
    rng = random.Random(seed)
    absolute = [float(job["resultABS"]) * float(job["wgt_frac"]) for job in jobs]
    total_abs = sum(absolute)
    # The upstream code loops over job['resultABS'] unweighted; wgt_frac=1
    # in the unsplit process stage. Enforce it here.
    if any(job["wgt_frac"] != 1.0 for job in jobs):
        raise ValueError("Nonunit wgt_frac: upstream allocation needs further audit")
    counts = [0 for _ in jobs]
    for _ in range(nevents):
        target = rng.random() * total_abs
        accumulated = 0.0
        idx = 0
        while idx < len(jobs) and accumulated < target:
            accumulated += float(jobs[idx]["resultABS"])
            idx += 1
        counts[idx - 1] += 1
    return total_abs, counts


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--process", required=True,
                    help="Existing absolute /data/.../delta441_backup/PROCNLO... path")
    args = ap.parse_args()
    proc = Path(args.process).expanduser().resolve(strict=True)
    if not str(proc).startswith("/data/aalida/AQP/Wjets/WENU/delta441_backup/"):
        ap.error("Expected Δ441 recovery process under /data/aalida/AQP/Wjets/WENU/delta441_backup/")
    status = proc / "SubProcesses" / "job_status.pkl"
    if not status.is_file():
        ap.error("No existing checkpoint: {}".format(status))
    with status.open("rb") as stream:
        jobs = pickle.load(stream)
    check_jobs(proc, jobs)

    vals = effective_run_card(proc / "Cards" / "run_card.dat")
    expected = {"nevents": "1000", "ickkw": "3",
                "nevt_job": "-1", "mcatnlo_delta": "true"}
    for key, want in expected.items():
        if vals.get(key, "").lower() != want:
            raise ValueError("Unexpected {}={!r}, expected {!r}".format(key, vals.get(key), want))
    fold = tuple(int(x) for x in re.split(r"[,\s]+", vals["folding"].strip()) if x)
    if fold != (4, 4, 1):
        raise ValueError("Unexpected folding {!r}".format(fold))
    if not math.isclose(float(vals["req_acc"].replace("D", "E")), 1e-4,
                        rel_tol=1e-12, abs_tol=0.0):
        raise ValueError("Unexpected req_acc")

    initial_seed, iseed, next_seed = get_seed(proc, vals)
    total_abs, counts = allocate(jobs, next_seed, 1000)
    active = [(jobs[i]["p_dir"], jobs[i]["channel"], count)
              for i, count in enumerate(counts) if count > 0]
    counts_sorted = sorted(counts, reverse=True)
    expected_total = sum(counts)
    if expected_total != 1000 or len(active) > 300:
        raise ValueError("Invalid allocation total")
    print("DELTA441_MINT2_ALLOCATION_PREFLIGHT_PASS")
    print("Recovered GF jobs:", len(jobs))
    print("Current randinit:", initial_seed)
    print("Run-card iseed:", iseed)
    print("Predicted next-run seed:", next_seed)
    print("Important: run setup may alter seed; actual allocation will be verified after preparation.")
    print("Total absolute weight:", "%.12g" % total_abs)
    print("Requested events:", expected_total)
    print("Event-producing GF jobs:", len(active))
    print("GF jobs with zero allocated events:", len(jobs) - len(active))
    print("Maximum events in any GF:", counts_sorted[0])
    print("Top 10 GF event allocations:")
    for p_dir, chan, n in sorted(active, key=lambda v: -v[2])[:10]:
        print("  {}/GF{}: {}".format(p_dir, chan, n))
    print("Storage is /data; Python code ran from its /home location.")
    print("No MadGraph jobs run; no files written.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, IndexError, pickle.UnpicklingError) as err:
        print("DELTA441_MINT2_PREFLIGHT_FAILED:", err, file=sys.stderr)
        sys.exit(1)
