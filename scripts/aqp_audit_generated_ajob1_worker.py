#!/usr/bin/env python3
"""Read-only audit of the ACTUAL generated MG5 aMC@NLO ajob1 worker contract.

Find worker script locations, stage arguments, copy behavior and observed
GF outputs BEFORE attempting an AQP completion-manifest hook.

No jobs, shell execution, checksum writes, MadGraph imports, grid changes or
Condor queries. Does NOT determine whether existing grids are numerically
valid. The output is evidence for worker-side implementation design only.
"""
import argparse
import json
from pathlib import Path
import re

CONFIGS = ("standard111", "delta111", "delta221", "delta441_backup")
NEEDED = {
    "argument_channel": r"(?m)^\s*channel\s*=\s*['\"]?\$1\b",
    "argument_run_mode": r"(?m)^\s*run_mode\s*=\s*['\"]?\$2\b",
    "argument_run_number": r"(?m)^\s*runnumber\s*=\s*['\"]?\$3\b",
    "argument_integration_step": r"(?m)^\s*integration_step\s*=\s*['\"]?\$4\b",
    "worker_exit_capture": r"(?m)^\s*status\s*=\s*\$\?\s*$",
    "stage_result_copy": r"(?m)^\s*cp\s+-f\s+res\.dat\s+res_\$integration_step\.dat\b",
    "stage_log_copy": r"(?m)^\s*cp\s+-f\s+log\.txt\s+log_MINT\$integration_step\.txt\b",
    "exit_uses_worker_status": r"(?m)^\s*exit\s+\$status\s*$",
}
STAGES = ("res_0.dat", "res_1.dat", "log_MINT0.txt", "log_MINT1.txt")


def analyze_text(content):
    """Flags are observational, not a proof of successful GF output."""
    return {key: bool(re.search(regex, content))
            for key, regex in NEEDED.items()}


def analyze_channel(channel):
    scripts = list(channel.glob("ajob1"))
    if len(scripts) != 1:
        return {"has_ajob1": False, "reason": "No unique P*/ajob1"}
    path = scripts[0]
    if path.is_symlink() or not path.is_file():
        return {"has_ajob1": False, "reason": "ajob1 is not a regular file"}
    if path.stat().st_size > 512 * 1024:
        return {"has_ajob1": False, "reason": "ajob1 exceeds read limit"}
    flags = analyze_text(path.read_text(encoding="utf-8", errors="replace"))
    stage_counts = {stage: 0 for stage in STAGES}
    examples = {stage: [] for stage in STAGES}
    # Only direct GF-like subdirs; don't recursively visit the whole process.
    for output_folder in channel.iterdir():
        if not output_folder.is_dir() or output_folder.is_symlink():
            continue
        if not output_folder.name.startswith(("G", "GF", "all_", "born_")):
            continue
        for stage in STAGES:
            candidate = output_folder / stage
            if candidate.is_file() and not candidate.is_symlink():
                stage_counts[stage] += 1
                if len(examples[stage]) < 2:
                    examples[stage].append(str(candidate))
    return {
        "has_ajob1": True, "worker": str(path),
        "worker_patterns": flags,
        "observed_stage_file_counts": stage_counts,
        "examples": examples,
        "copy_result_checked_by_exit_code": bool(re.search(
            r"(?m)^\s*cp\s+-f\s+res\.dat\s+res_\$integration_step\.dat\s*(?:\|\||&&|;)\s*(?:exit|return)", path.read_text(errors="replace"))),
        "request_id_present": "AQP_REQUEST_ID" in path.read_text(errors="replace"),
    }


def audit_config(base, config):
    process = base / config / "PROCNLO_loop_sm-no_b_mass_0"
    folder = process / "SubProcesses"
    if not folder.is_dir():
        return {"config": config, "present": False, "error": "No generated SubProcesses directory"}
    channels = sorted(p for p in folder.glob("P*") if p.is_dir() and not p.is_symlink())
    reports = [analyze_channel(p) for p in channels]
    valid = [x for x in reports if x["has_ajob1"]]
    pattern_consistency = {
        key: sum(bool(x["worker_patterns"].get(key)) for x in valid)
        for key in NEEDED
    }
    stage_total = {stage: sum(x["observed_stage_file_counts"][stage] for x in valid)
                   for stage in STAGES}
    return {
        "config": config, "present": True,
        "process": str(process), "channel_dirs": len(channels),
        "channels_with_ajob1": len(valid),
        "worker_pattern_counts": pattern_consistency,
        "stage_result_totals": stage_total,
        "example_channels": reports[:4],
        "observed_worker_request_identity_count": sum(x["request_id_present"] for x in valid),
        "unchecked_result_copy_count": sum(not x["copy_result_checked_by_exit_code"] for x in valid),
        "contract_verified": False,
        "reason": "Observation only: required_output mapping, job provenance, and worker-side manifest publication still need validation",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--report", type=Path,
                        help="Optional NEW report path outside production; never overwrite")
    args = parser.parse_args()
    base = args.base.resolve(strict=True)
    if not base.is_dir():
        parser.error("Base is not a directory")
    reports = {name: audit_config(base, name) for name in CONFIGS}
    summary = {
        "audit": "AQP_MG3511_GENERATED_AJOB1_WORKER_READ_ONLY",
        "production_files_modified": False,
        "live_htcondor_calls": 0,
        "worker_contract_approved": False,
        "configurations": reports,
    }
    for name, entry in reports.items():
        print("WORKER_AUDIT", name, "channels", entry.get("channel_dirs", 0),
              "ajob1", entry.get("channels_with_ajob1", 0),
              "stage_files", entry.get("stage_result_totals", {}),
              flush=True)
    if args.report is not None:
        destination = args.report.expanduser().absolute()
        if destination.exists() or destination.is_symlink():
            parser.error("Report path already exists; refusing overwrite")
        if str(destination).startswith("/cvmfs/") or "/AQP/Wjets/" in str(destination):
            parser.error("Refusing report inside production/CVMFS")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("x", encoding="utf-8") as stream:
            json.dump(summary, stream, indent=2, sort_keys=True)
            stream.write("\n")
        print("WORKER_AUDIT_REPORT", destination)
    print("WORKER_CONTRACT_APPROVED False (audit only)")
    return 0 if all(x.get("present") and x.get("channels_with_ajob1")
                    for x in reports.values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
