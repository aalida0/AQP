#!/usr/bin/env python3
"""Compare trusted local MG5 3.5.11 checkpoints; no MG invocation or writes.

Run from /home. WARNING: pickle.load is unsafe for untrusted files.
Read ONLY locally generated checkpoint files that you own/trust.
"""
import argparse
import math
import pickle
from pathlib import Path


def get_jobs(path):
    with path.open("rb") as stream:
        jobs = pickle.load(stream)
    if not isinstance(jobs, list) or not all(isinstance(j, dict) for j in jobs):
        raise ValueError("Checkpoint must contain a list of job dicts: {}".format(path))
    return jobs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recovered", required=True, help="Full path to new delta441 job_status.pkl")
    parser.add_argument("--reference", required=True, help="Full path to trusted standard111 job_status.pkl")
    args = parser.parse_args()

    recovered_path = Path(args.recovered).expanduser().resolve(strict=True)
    reference_path = Path(args.reference).expanduser().resolve(strict=True)
    jobs = get_jobs(recovered_path)
    refs = get_jobs(reference_path)
    if not jobs or not refs:
        raise ValueError("Empty checkpoint")

    original_keys = set().union(*(j.keys() for j in refs))
    keys_new = set().union(*(j.keys() for j in jobs))
    missing = sorted(original_keys - keys_new)
    extra = sorted(keys_new - original_keys)
    required = {
        "p_dir", "channel", "split", "accuracy", "niters", "npoints",
        "mint_mode", "run_mode", "wgt_frac", "dirname", "resultABS",
        "errorABS", "result", "error", "niters_done", "npoints_done",
        "time_spend", "nevents", "err_percABS", "err_perc",
    }

    problems = []
    if len(jobs) != 300:
        problems.append("Expected 300 Delta441 jobs; got {}".format(len(jobs)))
    if missing:
        problems.append("Keys present in reference but absent in reconstructed pickle: {}".format(missing))
    if not required.issubset(keys_new):
        problems.append("Missing required fields: {}".format(sorted(required - keys_new)))
    pairs = set()
    for i, job in enumerate(jobs):
        path = Path(job["dirname"])
        pair = (job["p_dir"], job["channel"])
        if pair in pairs:
            problems.append("Duplicate job: {}".format(pair))
        pairs.add(pair)
        if job["mint_mode"] != 2 or job["run_mode"] != "all" or job["split"] != 0:
            problems.append("Wrong MINT2 metadata at index {}".format(i))
        if not str(path).startswith("/data/"):
            problems.append("Job directory outside /data: {}".format(path))
        res = path / "res_1.dat"
        if not res.is_file():
            problems.append("Missing res_1.dat for {}".format(path))
        if not all(math.isfinite(float(job[k])) for k in ("resultABS", "errorABS", "result", "error")):
            problems.append("Nonfinite numerical field at index {}".format(i))
    order_ok = all(a["errorABS"] >= b["errorABS"]
                   for a, b in zip(jobs, jobs[1:]))
    if not order_ok:
        problems.append("Jobs not ordered by decreasing errorABS")

    print("Delta441 jobs:", len(jobs), "reference jobs:", len(refs))
    print("Recovered key count:", len(keys_new), "reference key count:", len(original_keys))
    print("New-only keys:", extra or "(none)")
    print("Reference-only keys:", missing or "(none)")
    print("Sorted by descending errorABS:", order_ok)
    print("All Delta441 directories on /data:", all(str(j["dirname"]).startswith("/data/") for j in jobs))
    print("Sum ABS:", "%.12g" % sum(j["resultABS"] for j in jobs))
    print("Sum signed:", "%.12g" % sum(j["result"] for j in jobs))
    if problems:
        print("CHECKPOINT_SCHEMA_REVIEW_NEEDED")
        for issue in problems[:25]:
            print(" -", issue)
        return 1
    print("CHECKPOINT_SCHEMA_PASS")
    print("No MG executables run; no data changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
