#!/usr/bin/env python3
"""Summarize MadGraph stages and matching HTCondor history for one gridpack run."""
import argparse
import csv
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
from datetime import datetime, timedelta

STAGES = {"Setting up grids": "grid", "Computing upper envelope": "envelope",
          "Generating events": "generation", "Doing reweight": "reweight"}
FIELDS = ("ClusterId", "ProcId", "Iwd", "Cmd", "Args", "QDate", "JobStartDate",
          "CompletionDate", "RemoteUserCpu", "RemoteSysCpu", "RemoteWallClockTime",
          "NumJobStarts", "JobStatus", "ExitCode", "RequestCpus")
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
        return [], None
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
    return list(totals.values()), pre_grid


def history(run, start_epoch):
    owner = os.environ.get("USER") or run.owner()
    # The unique run path, not the username alone, identifies these workers.
    prefix = re.escape(str(run.resolve()) + "/")
    cond = (f'Owner == {json.dumps(owner)} && '
            f'regexp({json.dumps("^" + prefix)}, Iwd)')
    if start_epoch:
        cond += f" && QDate >= {int(start_epoch) - 300}"
    cmd = ["condor_history", "-match", "0", "-constraint", cond, "-af:t", *FIELDS]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90, check=True)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        return [], str(exc)
    jobs = []
    for line in proc.stdout.splitlines():
        cols = line.split("\t")
        if len(cols) != len(FIELDS):
            return [], "Unexpected condor_history tabular format"
        ad = dict(zip(FIELDS, cols))
        if not ad["Iwd"].startswith(str(run.resolve()) + "/"):
            continue
        try:
            args = shlex.split(ad["Args"])
        except ValueError:
            args = []
        prog = Path(ad["Cmd"]).name
        if prog == "ajob1" and len(args) == 4 and args[-1] in ("0", "1", "2"):
            stage = {"0": "grid", "1": "envelope", "2": "generation"}[args[-1]]
        elif "reweight" in prog:
            stage = "reweight"
        else:
            stage = "other"
        cpu1 = number(ad["RemoteUserCpu"])
        cpu2 = number(ad["RemoteSysCpu"])
        jobs.append({"job_id": ad["ClusterId"] + "." + ad["ProcId"], "stage": stage,
                     "cpu_seconds": cpu1 + cpu2 if cpu1 is not None and cpu2 is not None else None,
                     "remote_wall_seconds": number(ad["RemoteWallClockTime"]),
                     "starts": number(ad["NumJobStarts"], int),
                     "success": ad["JobStatus"] == "4" and ad["ExitCode"] == "0",
                     "iwd": ad["Iwd"]})
    return jobs, None


def report(run, out):
    timing = read_kv(run / "timing.txt")
    controller = read_kv(run / "controller_cpu.txt")
    start = number(timing.get("start_epoch"), int)
    spans, pre_grid = stages_from_log(run / "log.generate", start, number(timing.get("end_epoch"), int))
    jobs, error = history(run, start)
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
                            j["starts"] == 1 for j in group))
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
    worker_complete = bool(spans) and all(x["accounting_complete"] for x in summary
                                          if x["stage"] != "other")
    worker_cpu = sum(x["reported_cpu_seconds"] for x in summary
                     if x["reported_cpu_seconds"] is not None)
    result = {
        "run": str(run), "transform_exit": number(timing.get("transform_exit"), int),
        "result_exit": number(timing.get("result_exit"), int),
        "transform_wall_seconds": number(timing.get("wall_seconds")),
        "pre_grid_stage_seconds": pre_grid,
        "controller_cpu_seconds": cpu, "worker_history_query_error": error,
        "history_worker_count": len(jobs), "worker_accounting_complete": worker_complete,
        "remote_cpu_seconds": worker_cpu if worker_complete else None,
        "total_cpu_seconds": cpu + worker_cpu if cpu is not None and worker_complete else None,
        "stages": summary,
        "notes": ["CPU values are reported by Condor ClassAds, not a sum of worker wall times.",
                  "Restart count is a lower bound from NumJobStarts; eviction timestamps are unavailable.",
                  "Runs with worker restarts are marked incomplete without per-attempt CPU accounting.",
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
