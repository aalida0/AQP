#!/usr/bin/env python3
"""Summarize MadGraph stages and matching HTCondor history for one gridpack run."""
import argparse
import csv
import json
import os
from pathlib import Path
import re
import subprocess
from datetime import datetime, timedelta

STAGES = {"Setting up grids": "grid", "Computing upper envelope": "envelope",
          "Generating events": "generation", "Doing reweight": "reweight"}
FIELDS = ("ClusterId", "ProcId", "Iwd", "Cmd", "Args", "QDate", "JobStartDate",
          "CompletionDate", "RemoteUserCpu", "RemoteSysCpu",
          "CumulativeRemoteUserCpu", "CumulativeRemoteSysCpu",
          "RemoteWallClockTime", "NumJobStarts", "JobStatus", "ExitCode", "RequestCpus")
TIME = re.compile(r"\b(\d\d):(\d\d):(\d\d)\b")
DONE = re.compile(r"Completed:\s*(\d+)")


def number(value, typ=float):
    try:
        return typ(value)
    except (TypeError, ValueError):
        return None


def read_kv(path):
    if not path.exists():
        return {}
    return dict(line.strip().split("=", 1) for line in path.read_text().splitlines()
                if "=" in line)


def stages_from_log(path, start_epoch, end_epoch=None):
    if not path.exists():
        return [], None, []
    stages, active = [], None
    day = datetime.fromtimestamp(start_epoch).date() if start_epoch else datetime.now().date()
    last_clock = None
    for line in path.read_text(errors="replace").splitlines():
        m = TIME.search(line)
        if not m:
            continue
        clock = sum(int(x) * mult for x, mult in zip(m.groups(), (3600, 60, 1)))
        if last_clock is not None and clock < last_clock - 43200:
            day += timedelta(days=1)
        last_clock = clock
        stamp = datetime.combine(day, datetime.min.time()) + timedelta(seconds=clock)
        stage = next((name for phrase, name in STAGES.items() if phrase in line), None)
        if stage:
            if active and active.get("end") is None:
                active["end"] = stamp
            active = {"stage": stage, "start": stamp, "end": None, "completed_workers": None}
            stages.append(active)
        if active:
            count = DONE.search(line)
            if count:
                active["completed_workers"] = max(active["completed_workers"] or 0, int(count[1]))
            if "All jobs finished" in line and active["end"] is None:
                active["end"] = stamp
    first_grid = next((span["start"] for span in stages if span["stage"] == "grid"), None)
    pre_grid = round((first_grid - datetime.fromtimestamp(start_epoch)).total_seconds()) if (first_grid and start_epoch) else None
    if pre_grid is not None and not (0 <= pre_grid <= (end_epoch - start_epoch + 300 if end_epoch else 86400)):
        pre_grid = None  # Log timezone differs from the machine parsing it.
    totals = {}
    for span in stages:
        stage = span["stage"]
        row = totals.setdefault(stage, {"stage": stage, "wall_seconds": 0,
                                         "expected_workers": 0, "span_count": 0})
        row["span_count"] += 1
        row["wall_seconds"] += int((span["end"] - span["start"]).total_seconds()) if span["end"] else 0
        row["expected_workers"] += span["completed_workers"] or 0
    intervals = [{"stage": x["stage"], "start_epoch": int(x["start"].timestamp()),
                  "end_epoch": int(x["end"].timestamp()) if x["end"] else None}
                 for x in stages]
    return list(totals.values()), pre_grid, intervals


def history(run, start_epoch, end_epoch, intervals):
    owner = os.environ.get("USER") or run.owner()
    # Restrict the server-side history scan to this unique workspace.
    # Anchor the following slash: run-AB must never match run-ABCD.
    root = str(run.resolve()) + os.sep
    pattern = json.dumps("^" + re.escape(root))
    constraint = ("Owner == " + json.dumps(owner) +
                  " && (regexp(" + pattern + ", Iwd) || regexp(" +
                  pattern + ", Cmd))")
    if start_epoch:
        constraint += f" && QDate >= {start_epoch - 300}"
    if end_epoch:
        constraint += f" && QDate <= {end_epoch + 300}"
    # Never use -match 0: that is a zero-result limit on some HTCondor versions.
    limit = 10000
    cmd = ["condor_history", "-constraint", constraint, "-limit", str(limit),
           "-json", "-attributes", ",".join(FIELDS)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=True)
        ads = json.loads(proc.stdout)
        if not isinstance(ads, list):
            return [], "HTCondor history JSON is not an array", 0
        if len(ads) == limit:
            return [], "HTCondor history result limit reached; narrow the query", len(ads)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired,
            ValueError) as exc:
        return [], f"HTCondor history query failed: {exc}", 0

    jobs = []
    for ad in ads:
        if not isinstance(ad, dict):
            return [], "Unexpected HTCondor history JSON record", len(ads)
        # Require exact run provenance. Never include unrelated users' jobs.
        iwd = str(ad.get("Iwd") or "")
        prog = str(ad.get("Cmd") or "")
        if not iwd.startswith(root) and not prog.startswith(root):
            continue
        # ajob1's final argument is the native MadGraph MINT phase
        # (0: grid, 1: upper envelope, 2: event generation).
        # This is more reliable than queue timestamps, which can fall
        # outside MadGraph's printed stage boundaries.
        args = str(ad.get("Args") or "").split()
        if Path(prog).name == "ajob1" and len(args) == 4:
            stage = {"0": "grid", "1": "envelope", "2": "generation"}.get(
                args[-1], "other")
        elif "reweight" in Path(prog).name:
            stage = "reweight"
        else:
            stage = "other"
        starts = number(ad.get("NumJobStarts"), int)
        cpu1 = number(ad.get("CumulativeRemoteUserCpu"))
        cpu2 = number(ad.get("CumulativeRemoteSysCpu"))
        if cpu1 is None or cpu2 is None:
            # Non-cumulative fields omit CPU lost to eviction.
            cpu1 = number(ad.get("RemoteUserCpu")) if starts == 1 else None
            cpu2 = number(ad.get("RemoteSysCpu")) if starts == 1 else None
        status = number(ad.get("JobStatus"), int)
        exit_code = number(ad.get("ExitCode"), int)
        jobs.append({"job_id": f'{ad.get("ClusterId")}.{ad.get("ProcId")}',
                     "stage": stage,
                     "cpu_seconds": cpu1 + cpu2 if cpu1 is not None and cpu2 is not None else None,
                     "remote_wall_seconds": number(ad.get("RemoteWallClockTime")),
                     "starts": starts,
                     "success": status == 4 and exit_code == 0,
                     "iwd": iwd})
    return jobs, None, len(ads)


def report(run, out):
    timing = read_kv(run / "timing.txt")
    controller = read_kv(run / "controller_cpu.txt")
    start = number(timing.get("start_epoch"), int)
    end = number(timing.get("end_epoch"), int)
    spans, pre_grid, intervals = stages_from_log(run / "log.generate", start, end)
    jobs, error, candidates = history(run, start, end, intervals)
    expected = {x["stage"]: x["expected_workers"] for x in spans}
    summary = []
    for name in ("grid", "envelope", "generation", "reweight", "other"):
        group = [j for j in jobs if j["stage"] == name]
        span = next((x for x in spans if x["stage"] == name), {})
        if not group and not span:
            continue
        required = expected.get(name) or None
        observed = len(group)
        complete = bool(required and observed == required and
                        all(j["success"] and j["cpu_seconds"] is not None and
                            j["starts"] is not None for j in group))
        known_cpu = sum(j["cpu_seconds"] for j in group if j["cpu_seconds"] is not None)
        known_wall = sum(j["remote_wall_seconds"] for j in group if j["remote_wall_seconds"] is not None)
        starts = sum(max(0, j["starts"] - 1) for j in group if j["starts"] is not None)
        summary.append({"stage": name, "wall_seconds": span.get("wall_seconds"),
                        "expected_workers": required, "history_workers": observed,
                        "reported_cpu_seconds": known_cpu if complete else None,
                        "observed_cpu_seconds": known_cpu if group else None,
                        "observed_remote_wall_seconds": known_wall if group else None,
                        "restart_lower_bound": starts if group else None,
                        "accounting_complete": complete})
    user = number(controller.get("controller_user_cpu_seconds"))
    system = number(controller.get("controller_system_cpu_seconds"))
    cpu = user + system if user is not None and system is not None else None
    worker_complete = bool(spans and jobs and error is None
                           and all(x["accounting_complete"] for x in summary)
                           and len(jobs) == sum(x["expected_workers"] for x in spans))
    worker_cpu = sum(x["reported_cpu_seconds"] for x in summary
                     if x["reported_cpu_seconds"] is not None)
    result = {
        "run": str(run), "start_epoch": start, "end_epoch": end,
        "worker_job_ids": sorted(j["job_id"] for j in jobs),
        "transform_exit": number(timing.get("transform_exit"), int),
        "result_exit": number(timing.get("result_exit"), int),
        "transform_wall_seconds": number(timing.get("wall_seconds")),
        "pre_grid_stage_seconds": pre_grid,
        "controller_cpu_seconds": cpu, "worker_history_query_error": error,
        "history_worker_count": len(jobs), "history_candidates_in_time_window": candidates,
        "worker_stage_assignment": "MadGraph ajob1 final argument (0/1/2)",
        "worker_accounting_complete": worker_complete,
        "remote_cpu_seconds": worker_cpu if worker_complete else None,
        "total_cpu_seconds": cpu + worker_cpu if cpu is not None and worker_complete else None,
        "stages": summary,
        "notes": ["MadGraph ajob1 phase argument identifies grid/envelope/generation.",
                  "CumulativeRemote*Cpu is preferred to include evicted attempts.",
                  "Restart count is a lower bound from NumJobStarts; eviction timestamps are unavailable.",
                  "Restarted workers without cumulative CPU values are marked incomplete.",
                  "Null CPU totals mean incomplete worker accounting, not zero CPU use."]}
    out.mkdir(parents=True, exist_ok=True)
    (out / "timing_summary.json").write_text(json.dumps(result, indent=2) + "\n")
    cols = ["stage", "wall_seconds", "expected_workers", "history_workers",
            "reported_cpu_seconds", "observed_cpu_seconds",
            "observed_remote_wall_seconds", "restart_lower_bound", "accounting_complete"]
    with (out / "timing_summary.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=cols)
        writer.writeheader()
        writer.writerows(summary)
    print("TIMING_REPORT", out / "timing_summary.json")
    print("WORKER_ACCOUNTING", "COMPLETE" if worker_complete else "INCOMPLETE")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    report(args.run.resolve(strict=True), args.output or args.run)
