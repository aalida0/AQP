#!/usr/bin/env python3
"""Stage and execute ONE actual MG5 MINT0 ajob1 worker from an archived Condor job.

Uses the archived Condor job's exact transfer-input list, NOT a full process copy.
Run via AthGeneration 23.6.63 with pinned AQP bootstrap enabled.
No changes to the original /scratch process or existing held/removed jobs.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time


def history(jobid):
    result = subprocess.run(
        ["condor_history", jobid, "-af", "Iwd", "TransferInput", "TransferOutput"],
        check=True, capture_output=True, text=True,
    )
    rows = [r.strip() for r in result.stdout.splitlines() if r.strip()]
    if len(rows) != 1:
        raise RuntimeError("Expected exactly one archived Condor job: " + jobid)
    fields = rows[0].split(None, 2)
    if len(fields) != 3:
        raise RuntimeError("Invalid archived Condor transfer metadata: " + rows[0])
    iwd, inputs, outputs = fields
    if outputs != "GF1.0":
        raise RuntimeError("Unexpected output contract: " + outputs)
    if Path(iwd).name != "P0_uux_mummup":
        raise RuntimeError("Unexpected archived subprocess: " + iwd)
    return Path(iwd), [Path(p) for p in inputs.split(",")], outputs


def prepare(jobid):
    iwd, sources, output = history(jobid)
    proc = iwd.parents[1]
    if not str(proc).startswith("/scratch/") or proc.name != "PROCNLO_loop_sm-no_b_mass_0":
        raise RuntimeError("Archived process is not the expected /scratch input")
    home = Path.home().resolve()
    base = home / "AQP" / "condor-one-worker"
    base.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="mint0-", dir=base))
    cwd = stage / iwd.relative_to(proc)
    cwd.mkdir(parents=True)
    source_list = sources + [iwd / "ajob1"]
    for src in source_list:
        try:
            rel = src.relative_to(proc)
        except ValueError as exc:
            raise RuntimeError("Unexpected source outside process: " + str(src)) from exc
        if not src.exists():
            raise RuntimeError("Missing original worker input: " + str(src))
        dst = stage / rel
        if dst.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst, symlinks=False)
        else:
            shutil.copy2(src, dst, follow_symlinks=True)
    if (cwd / "GF1.0" / "results.dat").exists():
        raise RuntimeError("Existing results.dat would invalidate worker test")
    if not (cwd / "ajob1").is_file():
        raise RuntimeError("Missing staged executable")
    (stage / "guard").mkdir()
    metadata = {
        "jobid_source": jobid,
        "cwd": str(cwd),
        "args": ["1.0", "F", "0", "0"],
        "input_files": [str(stage / src.relative_to(proc)) for src in sources],
        "output_files": [output],
        "required_output": ["GF1.0/log_MINT0.txt", "GF1.0/results.dat"],
    }
    (stage / "worker.json").write_text(json.dumps(metadata, indent=2) + "\n")
    size = shutil.disk_usage(home)
    print("ONE_WORKER_STAGED", stage)
    print("STAGED_DISK_USAGE", subprocess.check_output(
        ["du", "-sh", str(stage)], text=True).strip())
    print("HOST_SHARED_FREE_GB", round(size.free / 1e9, 1))
    print("NOTE: filesystem free space is not your personal quota.")
    print("NO_JOBS_SUBMITTED")
    print("TO_RUN: python3 smoke/1jet/one_real_worker.py run", stage)


def run(stage):
    import madgraph.various.cluster as cluster
    if not (hasattr(cluster, "_aqp_claim") and hasattr(cluster, "_aqp_states")):
        raise RuntimeError("AQP pinned cluster patch was NOT loaded")
    if not os.environ.get("AQP_CLUSTER_CANDIDATE"):
        raise RuntimeError("AQP_CLUSTER_CANDIDATE is unset")
    stage = stage.resolve(strict=True)
    home = (Path.home() / "AQP" / "condor-one-worker").resolve()
    if not stage.is_relative_to(home):
        raise RuntimeError("Worker stage must be under " + str(home))
    data = json.loads((stage / "worker.json").read_text())
    cwd = Path(data["cwd"])
    if not cwd.is_dir() or not (cwd / "ajob1").exists():
        raise RuntimeError("Missing staged worker")
    if (stage / "jobid").exists():
        raise RuntimeError("Submission already attempted: " + str(stage / "jobid"))
    guard = stage / "guard"
    if list(guard.glob("*.intent")):
        raise RuntimeError("Existing submission guard; do not duplicate")
    os.environ["AQP_CONDOR_GUARD_DIR"] = str(guard)
    controller = cluster.CondorCluster(
        cluster_queue="None", cluster_nb_retry=0,
        cluster_retry_wait=120, cluster_status_update=(30, 5),
    )
    # Create a durable marker before submitting; a lost acknowledgement
    # must never cause a second submission from this command.
    (stage / "jobid").write_text("SUBMISSION_ATTEMPTED_NO_ACK\n")
    job = controller.submit2(
        str(cwd / "ajob1"), data["args"], cwd=str(cwd),
        stdout=str(stage / "worker.out"),
        stderr=str(stage / "worker.err"),
        log=str(stage / "worker.log"),
        input_files=data["input_files"],
        output_files=data["output_files"],
        required_output=data["required_output"],
    )
    (stage / "jobid").write_text(job + ".0\n")
    print("ONE_REAL_AJOB1_SUBMITTED", job, flush=True)
    print("STAGE", stage, flush=True)
    while True:
        try:
            status = controller.control(None)
        except Exception:
            print("WORKER_CONTROL_FAILED; inspect job and guard, do not resubmit", flush=True)
            raise
        print("ONE_REAL_AJOB1_STATUS", status, flush=True)
        if not controller.submitted_ids:
            for output in data["required_output"]:
                p = cwd / output
                if not p.is_file() or p.stat().st_size == 0:
                    raise RuntimeError("Required output missing after completion: " + str(p))
            if list(guard.glob("*.intent")):
                raise RuntimeError("Submission guard remained after success")
            print("ONE_REAL_AJOB1_PASS", flush=True)
            return
        time.sleep(10)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--source-job", default="4062447.0")
    launch = sub.add_parser("run")
    launch.add_argument("stage", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.source_job)
    else:
        run(args.stage)
