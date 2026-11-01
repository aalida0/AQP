#!/usr/bin/env python3
"""READ-ONLY replay of the 16 archived FxFx NLO reweight workers.

This command NEVER submits, removes, releases, or modifies Condor jobs and
NEVER changes the MadGraph process on disk. It exercises the patched
CondorCluster.control() against real history and existing outputs.
"""
import argparse
import os
from pathlib import Path
import subprocess


NAMES = (
    "events.lhe.rwgt",
    "reweight_xsec_events.output",
    "scale_pdf_dependence.dat",
)
FIRST = 4062653
LAST = 4062668


def load_history(ids):
    p = subprocess.run(
        ["condor_history", *ids, "-af", "ClusterId", "ProcId",
         "JobStatus", "ExitCode", "Iwd", "Cmd"],
        capture_output=True, text=True, check=True, timeout=90,
    )
    if p.stderr.strip():
        raise RuntimeError("Condor history warning: " + p.stderr.strip())
    data = {}
    for line in p.stdout.splitlines():
        parts = line.split(None, 5)
        if len(parts) != 6 or parts[0] not in ids or parts[0] in data:
            raise RuntimeError("Malformed/duplicate/out-of-range history: " + line)
        clusterid, procid, status, exitcode, cwd, program = parts
        if (procid, status, exitcode) != ("0", "4", "0"):
            raise RuntimeError("Archived job did not succeed: " + line)
        if Path(program).name != "reweight_xsec_events.local":
            raise RuntimeError("Unexpected archived program: " + program)
        data[clusterid] = Path(cwd)
    if set(data) != set(ids):
        raise RuntimeError("Incomplete archived reweight history: " +
                           repr(sorted(set(ids) - set(data))))
    return data


def replay(process):
    import madgraph.various.cluster as cluster

    if not all(hasattr(cluster, n) for n in
               ("_aqp_claim", "_aqp_states", "_aqp_output_contract")):
        raise RuntimeError("Experimental v3 Condor patch is not active")
    expected = (Path.home() / "AQP" / "condor-smoke" /
                "MG1jet-smoke.sviBub" / "PROCNLO_loop_sm-no_b_mass_0").resolve()
    if process.resolve(strict=True) != expected:
        raise RuntimeError("Replay requires the archived disposable process: " +
                           str(expected))

    ids = [str(n) for n in range(FIRST, LAST + 1)]
    job_cwds = load_history(ids)
    records = {}
    empty_summaries = 0
    for jobid, cwd in job_cwds.items():
        cwd = cwd.resolve(strict=True)
        if not cwd.is_relative_to(process.resolve()):
            raise RuntimeError("Archived job cwd outside isolated process: " + str(cwd))
        if cwd.parent.name.startswith("P") is False or not cwd.name.startswith("GF"):
            raise RuntimeError("Unexpected reweight channel path: " + str(cwd))
        executable = cwd / "reweight_xsec_events.local"
        if not executable.exists():
            raise RuntimeError("Missing reweight program: " + str(executable))
        nonempty, exists_only = cluster._aqp_output_contract(
            str(cwd), str(executable), NAMES)
        if (list(nonempty) != list(NAMES[:2]) or
                list(exists_only) != ["scale_pdf_dependence.dat"]):
            raise RuntimeError("V3 did not identify nominal reweight output contract: " +
                               repr((nonempty, exists_only)))
        for filename in nonempty:
            target = cwd / filename
            if not target.is_file() or target.stat().st_size == 0:
                raise RuntimeError("Missing/nonempty required event output: " + str(target))
        for filename in exists_only:
            target = cwd / filename
            if not target.is_file():
                raise RuntimeError("Missing required summary output: " + str(target))
            if target.stat().st_size == 0:
                empty_summaries += 1
        records[jobid] = dict(cwd=str(cwd), required_output=list(nonempty),
                              _aqp_exists_only=list(exists_only), nb_submit=0)

    if not empty_summaries:
        raise RuntimeError("No empty summary observed; cannot reproduce v2 false-negative")

    controller = cluster.CondorCluster(
        cluster_queue="None", cluster_nb_retry=0,
        cluster_retry_wait=120, cluster_status_update=(30, 5))
    controller.submitted_ids = ids.copy()
    controller.submitted = len(ids)
    controller.retry_args = records

    print("READ_ONLY_REPLAY", len(ids), "archived jobs", flush=True)
    print("ZERO_BYTE_SCALE_PDF_SUMMARIES", empty_summaries, flush=True)
    state = controller.control(None)  # Real condor_q/history; no submissions.
    print("V3_CONTROL_STATE", state, flush=True)
    if state != (0, 0, len(ids), 0) or controller.submitted_ids:
        raise RuntimeError("V3 completion replay did not acknowledge all workers")
    if controller.retry_args:
        raise RuntimeError("V3 retry tracking did not clean up")
    print("REWEIGHT_REPLAY_PASS", len(ids), "workers", flush=True)
    print("NO_CONDOR_SUBMISSION_OR_GENERATION_PERFORMED", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--process", type=Path,
                    default=Path.home() / "AQP" / "condor-smoke" /
                    "MG1jet-smoke.sviBub" / "PROCNLO_loop_sm-no_b_mass_0")
    args = ap.parse_args()
    replay(args.process)
