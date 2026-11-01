#!/usr/bin/env python3
"""Validate independent and overlapping gridpack timing reports (no submissions)."""
import argparse
import json
from pathlib import Path


def check(a, b):
    paths = [Path(a).resolve(strict=True), Path(b).resolve(strict=True)]
    reports = [json.loads(path.read_text()) for path in paths]
    assert paths[0] != paths[1], "Same timing report supplied twice"
    assert reports[0]["run"] != reports[1]["run"], "Identical run directory"
    for path, report in zip(paths, reports):
        assert report["transform_exit"] == report["result_exit"] == 0, path
        assert report["worker_accounting_complete"] is True, path
        ids = report["worker_job_ids"]
        assert ids and len(ids) == len(set(ids)), "Missing/duplicate worker IDs"
        assert len(ids) == report["history_worker_count"], path
        assert sum(s["history_workers"] for s in report["stages"]) == len(ids), path
        assert all(s["accounting_complete"] for s in report["stages"]), path
        assert len(list(path.parent.glob("mc_*GRID.tar.gz"))) == 1, path
    intersection = set(reports[0]["worker_job_ids"]) & set(reports[1]["worker_job_ids"])
    assert not intersection, "Worker IDs counted in both runs: " + str(sorted(intersection)[:5])
    starts = [r["start_epoch"] for r in reports]
    ends = [r["end_epoch"] for r in reports]
    assert all(isinstance(x, int) for x in starts + ends), "Missing run timestamps"
    overlap = min(ends) - max(starts)
    assert overlap > 0, "Runs did not overlap in wall time"
    print("CONCURRENT_GRIDPACKS_PASS")
    print("OVERLAP_SECONDS", overlap)
    for report in reports:
        print("RUN", report["run"], "WORKERS", report["history_worker_count"],
              "REMOTE_CPU_SECONDS", report["remote_cpu_seconds"])


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("report_a")
    p.add_argument("report_b")
    args = p.parse_args()
    check(args.report_a, args.report_b)
