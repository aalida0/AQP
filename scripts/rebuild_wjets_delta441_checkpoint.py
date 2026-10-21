#!/usr/bin/env python3
"""Rebuild missing MG5_aMC@NLO v3.5.11 MINT1 controller checkpoint, safely.

Run THIS script from /home; source/target heavy MG5 process trees live on /data.
This does NOT run any MadGraph executable or start integration/event generation.

Source implementation:
  mg5amcnlo/mg5amcnlo v3.5.11, madgraph/interface/amcatnlo_run_interface.py
  create_jobs_to_run (2062-2147), prepare_directories (2149-2181),
  append_the_results (2720-2755), collect_the_results (2253-2325).
  Reconstruct the checkpoint that --only_generation expects.

Default is read-only, even for the /data process directory.
--write-checkpoint creates ONLY SubProcesses/job_status.pkl and a JSON report.
No source files are overwritten and no other MG5 input files are modified.
"""
import argparse
import hashlib
import json
import math
import os
import pickle
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REQUIRED_GRID_FILES = ("mint_grids", "grid.MC_integer", "res_1.dat", "res.dat", "results.dat")
GF_PATTERN = re.compile(r"^GF[0-9]+(?:\.[0-9]+)?$")
P_PATTERN = re.compile(r"^P[0-9]+_[A-Za-z0-9_]+$")
SEVEN_VALUES = 7


def fail(reason):
    raise ValueError(reason)


def real(value, field, where):
    try:
        parsed = float(value.replace("D", "E").replace("d", "e"))
    except ValueError:
        fail("{}: {} not numeric: {!r}".format(where, field, value))
    if not math.isfinite(parsed):
        fail("{}: {} is not finite: {!r}".format(where, field, value))
    return parsed


def load_res(path):
    line = path.read_text(errors="replace").splitlines()
    if not line:
        fail("{}: empty res_1.dat".format(path))
    values = line[0].split()
    if len(values) < SEVEN_VALUES:
        fail("{}: need at least seven fields, got {}".format(path, len(values)))
    numbers = [real(v, "field {}".format(i + 1), path) for i, v in enumerate(values[:7])]
    for i in (4, 5):
        if numbers[i] < 0 or not numbers[i].is_integer():
            fail("{}: iterations/points must be nonnegative integers".format(path))
    if numbers[0] < 0 or numbers[1] < 0 or numbers[3] < 0 or numbers[6] < 0:
        fail("{}: negative absolute rate, uncertainty, or time".format(path))
    if len(values) > 7:
        # The MG driver consumes the first seven fields; preserve a warning
        # through its summary rather than dropping or reinterpreting data.
        pass
    return numbers


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def stage_configuration(process, allow_write):
    process = Path(process).expanduser().resolve(strict=True)
    if not process.is_dir() or process.name != "PROCNLO_loop_sm-no_b_mass_0":
        fail("Pass the full, existing PROCNLO_loop_sm-no_b_mass_0 directory")
    if not str(process).startswith("/data/"):
        fail("Safety: the recovery process must reside under /data (never write into /home)")
    sub = process / "SubProcesses"
    status = sub / "job_status.pkl"
    if status.exists() or status.is_symlink():
        fail("Checkpoint already exists; refusing to replace {}".format(status))
    subproc_file = sub / "subproc.mg"
    if not subproc_file.is_file():
        fail("Missing {}".format(subproc_file))
    pdirs = [x.strip() for x in subproc_file.read_text().splitlines() if x.strip()]
    if not pdirs or len(set(pdirs)) != len(pdirs):
        fail("Empty or repeated subprocess names in subproc.mg")
    jobs = []
    anomalous = []
    fingerprints = {}
    for p in pdirs:
        if not P_PATTERN.fullmatch(p):
            fail("Invalid subprocess name {!r}".format(p))
        ppath = sub / p
        channel_file = ppath / "channels.txt"
        if not channel_file.is_file():
            fail("Missing {}".format(channel_file))
        channel_lines = channel_file.read_text().splitlines()
        if not channel_lines:
            fail("Empty {}".format(channel_file))
        channels = channel_lines[0].split()
        if len(channels) != len(set(channels)):
            fail("Repeated channel in {}".format(channel_file))
        for channel in channels:
            gf_name = "GF" + channel
            if not GF_PATTERN.fullmatch(gf_name):
                fail("{}: invalid channel {!r}".format(channel_file, channel))
            gf = ppath / gf_name
            if not gf.is_dir():
                fail("Missing GF target {}".format(gf))
            for name in REQUIRED_GRID_FILES:
                pfile = gf / name
                if not pfile.is_file() or pfile.stat().st_size == 0:
                    fail("{}: absent or zero-length required artifact".format(pfile))
            nums = load_res(gf / "res_1.dat")
            grids = (gf / "mint_grids").read_text(errors="replace")
            if not all(re.search(r"(?m)^\s*{}\s".format(key), grids)
                       for key in ("MAX", "SUM", "QSM", "SPE")):
                fail("{}: missing MINT1 record labels".format(gf / "mint_grids"))
            # The MG driver needs this exact set of basic NLO+PS job keys.
            # append_the_results() recomputes numerical values from res_1.dat
            # when --only_generation is invoked. We also include them here for
            # parity with the original stage-1 checkpoint.
            job = {
                "p_dir": p,
                "channel": channel,
                "split": 0,
                "accuracy": 0.2,   # overwritten by MG step-1 result collection
                "niters": 12,     # historical MINT0 default (not used in MINT2)
                "npoints": -1,   # historical MINT0 default (not used in MINT2)
                "mint_mode": 2,  # after collecting MINT1, before generation
                "run_mode": "all",
                "wgt_frac": 1.0,
                "dirname": str(gf),
                "resultABS": nums[0],
                "errorABS": nums[1],
                "result": nums[2],
                "error": nums[3],
                "niters_done": int(nums[4]),
                "npoints_done": int(nums[5]),
                "time_spend": nums[6],
                "nevents": 0, # recomputed from genuine delta441 res_1.dat
                "err_percABS": (100 * nums[1] / nums[0] if nums[0] else 0.0),
                "err_perc": (100 * nums[3] / nums[2] if nums[2] else 0.0),
            }
            jobs.append(job)
            rel = "{}/{}".format(p, gf_name)
            fingerprints[rel] = sha256(gf / "res_1.dat")
            if nums[0] == 0:
                anomalous.append("{}: zero ABS contribution".format(rel))
    existing = [str(p.relative_to(sub)) for p in sub.glob("P*/GF*") if p.is_dir()]
    if len(jobs) != 300 or len(existing) != 300 or len(set(existing)) != 300:
        fail("Expected exactly 300 matching GF targets; reconstructed {}, existing {}".format(len(jobs), len(existing)))
    expected = set(fingerprints)
    if expected != set(existing):
        fail("GF directories and channel manifest differ: missing={} unexpected={}".format(
            sorted(expected - set(existing))[:10], sorted(set(existing) - expected)[:10]))
    if any(j["resultABS"] == 0 for j in jobs):
        fail("Zero-ABS channel present: upstream MG step-1 allocation divides by resultABS. "
             "Do not resume until audited: {}".format(anomalous[:20]))
    # v3.5.11 write_res_txt_file() sorts jobs before saving checkpoint.
    # MINT2 weighted assignment uses the same order.
    jobs.sort(key=lambda job: -job["errorABS"])
    cards = process / "Cards" / "run_card.dat"
    randinit = sub / "randinit"
    if not cards.is_file() or not randinit.is_file():
        fail("Missing run_card.dat or SubProcesses/randinit")
    rand = randinit.read_text(errors="replace").strip()
    if not re.fullmatch(r"r=\d+", rand):
        fail("Unexpected randinit format: {!r}".format(rand))
    card_text = cards.read_text(errors="replace")
    # The MG RunCardNLO parser lowercases names and the last occurrence wins.
    card_values = {}
    for line in card_text.splitlines():
        line = line.split("#", 1)[0].split("!", 1)[0]
        if "=" not in line:
            continue
        value, name = line.rsplit("=", 1)
        card_values[name.strip().lower()] = value.strip().lower()
    desired = {"nevents": "1000", "req_acc": "0.0001",
               "ickkw": "3", "mcatnlo_delta": "true", "nevt_job": "-1"}
    for key, wanted in desired.items():
        actual = card_values.get(key)
        if key == "req_acc":
            try:
                ok = math.isclose(float(actual.replace("d", "e")), 1e-4,
                                  rel_tol=1e-12, abs_tol=0)
            except (ValueError, AttributeError):
                ok = False
        else:
            ok = (actual == wanted)
        if not ok:
            fail("Run card {}: expected {}, found {}".format(key, wanted, actual))
    folding = [int(x) for x in re.split(r"[ ,]+", card_values.get("folding", ""))
               if x.isdigit()]
    if folding != [4, 4, 1]:
        fail("Unexpected delta441 folding: {}".format(card_values.get("folding")))
    def card_entries(key):
        return [line.strip() for line in card_text.splitlines()
                if re.match(r"^\s*[^#!\n]*=\s*{}\s*(?:[#!]|$)".format(re.escape(key)), line, re.I)]
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "recovery_mode": "WRITE_CHECKPOINT" if allow_write else "READ_ONLY",
        "mg_version": "v3.5.11",
        "process": str(process),
        "target_count": len(jobs),
        "subprocess_count": len(pdirs),
        "sum_signed": sum(job["result"] for job in jobs),
        "sum_abs": sum(job["resultABS"] for job in jobs),
        "quadrature_signed_error": math.sqrt(sum(job["error"] ** 2 for job in jobs)),
        "quadrature_abs_error": math.sqrt(sum(job["errorABS"] ** 2 for job in jobs)),
        "zero_abs_channels": 0,
        "negative_signed_channels": sum(job["result"] < 0 for job in jobs),
        "seed": rand,
        "run_card_sha256": sha256(cards),
        "effective_run_card": {key: card_values[key] for key in
                               ("nevents", "req_acc", "ickkw",
                                "mcatnlo_delta", "folding", "nevt_job")},
        "checkpoint_sorting": "descending errorABS (MG5 v3.5.11)",
        "run_card_config": {
            key: card_entries(key)
            for key in ("nevents", "req_acc", "folding", "ickkw", "mcatnlo_delta", "nevt_job")
        },
        "res_1_sha256": fingerprints,
    }
    if not allow_write:
        return status, jobs, manifest

    # Status is written only within copied process on /data.
    # Use an atomic hard-link, never overwrite existing checkpoint.
    with tempfile.NamedTemporaryFile(
        mode="wb", dir=sub, prefix=".job_status_recovery_", delete=False
    ) as stream:
        temp = Path(stream.name)
        try:
            pickle.dump(jobs, stream, protocol=2)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temp.unlink(missing_ok=True)
            raise
    try:
        os.link(temp, status)
    finally:
        temp.unlink(missing_ok=True)
    return status, jobs, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--process", required=True,
        help="Absolute /data/.../delta441_backup/PROCNLO_loop_sm-no_b_mass_0",
    )
    parser.add_argument(
        "--write-checkpoint", action="store_true",
        help="Explicitly create /data process/SubProcesses/job_status.pkl if absent",
    )
    parser.add_argument(
        "--report", help="Write JSON audit report under /data (never /home)",
    )
    args = parser.parse_args()
    if args.report:
        report_path = Path(args.report).expanduser().resolve()
        if not str(report_path).startswith("/data/"):
            parser.error("--report must be under /data")
        if report_path.exists() or report_path.is_symlink():
            parser.error("--report target already exists; refusing overwrite")
    try:
        status, jobs, manifest = stage_configuration(args.process, args.write_checkpoint)
    except (OSError, ValueError) as exc:
        print("RECOVERY_PRECHECK_FAILED:", exc, file=sys.stderr)
        return 1
    print("RECOVERY_PRECHECK_PASS")
    print("Process:", manifest["process"])
    print("MG5 version assumption:", manifest["mg_version"])
    print("GF targets / subprocesses:", manifest["target_count"], "/", manifest["subprocess_count"])
    print("sum ABS / sum signed:", "%.12g" % manifest["sum_abs"], "%.12g" % manifest["sum_signed"])
    print("quadrature ABS error:", "%.12g" % manifest["quadrature_abs_error"])
    print("negative signed channels:", manifest["negative_signed_channels"])
    print("randinit:", manifest["seed"])
    print("Effective MC@NLO-Delta:", manifest["effective_run_card"]["mcatnlo_delta"])
    print("Checkpoint job ordering:", manifest["checkpoint_sorting"])
    print("Run card configuration:")
    for key, lines in manifest["run_card_config"].items():
        print("  {}: {}".format(key, " ; ".join(lines) if lines else "NOT FOUND"))
    print("Checkpoint:", status)
    print("State:", "WRITTEN" if args.write_checkpoint else "NOT WRITTEN (audit-only)")
    if args.report:
        report = Path(args.report).expanduser().resolve()
        report.parent.mkdir(parents=True, exist_ok=True)
        with report.open("x") as out:
            json.dump(manifest, out, indent=2, sort_keys=True)
            out.write("\n")
        print("Audit report:", report)
    print("No MG executables invoked. No integration or event generation run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
