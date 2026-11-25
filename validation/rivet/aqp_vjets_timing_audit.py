#!/usr/bin/env python3
"""Read-only timing audit of exact EVNT/log pairs in the fresh Rivet merges."""
import argparse
import csv
import json
import math
from pathlib import Path
import re
import tarfile

from aqp_nwf_10logs import pythia_counts, pythia_reported_efficiency
from aqp_vjets_generator_xsec_evidence import decode_log
from aqp_vjets_v2_xsec_match import job_key

ROOT = Path("/data/aalida/AQP_Rivet_full/outputs/fresh_rivet_20261124")
KEYS = ("gen_wall_seconds_gnu", "gen_wall_seconds",
        "gen_user_cpu_seconds", "gen_system_cpu_seconds", "gen_exit_code")


def timing_fields(text):
    values = {}
    for key in KEYS:
        found = re.findall(r"(?m)^\s*" + key + r"\s*=\s*(\d+(?:\.\d+)?)\s*$", text)
        if found:
            vals = {float(v) for v in found}
            if len(vals) != 1:
                raise ValueError("Conflicting timing values for " + key)
            values[key] = vals.pop()
    return values


def measured_timing(path, log, timing_path=None, expected_events=None):
    """Use the worker's actual GNU time records, never infer CPU from wall."""
    values = timing_fields(log)
    sources = ["generator_log"] if values else []
    if timing_path is not None:
        timing_text = timing_path.read_text()
        requested = re.findall(r"(?m)^requested_accepted_events=(\d+)\s*$", timing_text)
        if expected_events is not None and requested != [str(expected_events)]:
            raise ValueError("Timing record event target mismatch: " + str(timing_path))
        found = timing_fields(timing_text)
        if found.get("gen_exit_code") != 0:
            raise ValueError("Timing record lacks successful exit: " + str(timing_path))
        for key, value in found.items():
            if key in values and values[key] != value:
                raise ValueError("Conflicting separate timing for " + key)
            values[key] = value
        sources.append(str(timing_path))
    elif tarfile.is_tarfile(path):
        with tarfile.open(path, "r:*") as tf:
            for member in tf.getmembers():
                name = Path(member.name).name
                if not member.isfile() or name not in (
                    "generation_timing.txt", "gen_tf_time.txt", "payload.stdout", "run.log"
                ):
                    continue
                stream = tf.extractfile(member)
                found = timing_fields(stream.read().decode("utf-8", "replace"))
                if found:
                    for key, value in found.items():
                        if key in values and values[key] != value:
                            raise ValueError("Conflicting archive timing for " + key)
                        values[key] = value
                    sources.append(name)
    if values.get("gen_exit_code", 0) != 0:
        raise ValueError("Nonzero generation exit code")
    wall = values.get("gen_wall_seconds_gnu", values.get("gen_wall_seconds"))
    cpu = None
    if all(k in values for k in ("gen_user_cpu_seconds", "gen_system_cpu_seconds")):
        cpu = values["gen_user_cpu_seconds"] + values["gen_system_cpu_seconds"]
    return (wall if wall and wall > 0 else None,
            cpu if cpu and cpu > 0 else None, ",".join(sources))


def summarize(rows, key):
    good = [r for r in rows if r[key] is not None]
    n = sum(r["entries"] for r in good)
    sw = math.fsum(r["sumW"] for r in good)
    sw2 = math.fsum(r["sumW2"] for r in good)
    neff = sw*sw/sw2 if sw2 > 0 else 0
    total = math.fsum(r[key] for r in good)
    return len(good), n, total if good else None, total/n if n else None, total/neff if neff else None


def fmt(x):
    return "NA" if x is None else f"{x:.6g}"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--timing-root", type=Path, default=Path("/data/aalida/AQP/aqp_grid_timing"))
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((a.root/"production_manifest.json").read_text())["samples"]
    individual, summary, evidence = [], [], []
    for sample, data in manifest.items():
        merged = json.loads((a.root/"merged"/(sample.replace("/", "_")+"_fresh.yoda.json")).read_text())
        if merged["metadata_check"] != "PASS":
            raise ValueError("Unvalidated merge " + sample)
        excluded = {x["evnt"] for x in merged["excluded"]}
        timing_by_id = {}
        for path in (a.timing_root/sample).rglob("*.generation_timing.txt"):
            key = job_key(path)
            if key is None:
                continue
            if key in timing_by_id:
                raise ValueError("Duplicate timing record " + str(key))
            timing_by_id[key] = path
        rows = []
        for r in data["included"]:
            if r["evnt"] in excluded:
                continue
            receipt = a.root/"full"/sample/"yoda"/r["evnt"].replace(".EVNT.pool.root", ".yoda.json")
            d = json.loads(receipt.read_text())
            if d["evnt"] != r["evnt"] or d["entries"] != r["entries"] or d["sample"] != sample:
                raise ValueError("Receipt mismatch " + str(receipt))
            row = dict(sample=sample, evnt=r["evnt"], log=r["log"], entries=d["entries"],
                       sumW=d["sumW"], sumW2=d["sumW2"], wall_s=None, cpu_s=None,
                       timing_source="", tried=None, accepted=None, reported_eff=None, error="")
            try:
                path = Path(r["log"])
                log = decode_log(path)
                row["wall_s"], row["cpu_s"], row["timing_source"] = measured_timing(
                    path, log, timing_by_id.get(job_key(r["evnt"])), r["entries"])
                tried, _, accepted = pythia_counts(log)
                if tried and accepted and 0 < accepted <= tried and abs(accepted-row["entries"]) <= max(5, 0.05*row["entries"]):
                    row.update(tried=tried, accepted=accepted)
                row["reported_eff"] = pythia_reported_efficiency(log)
                if not rows:
                    evidence.append(f"\n=== {sample}: {path} ===")
                    if tarfile.is_tarfile(path):
                        with tarfile.open(path, "r:*") as tf:
                            evidence.append("ARCHIVE_MEMBERS: " + ", ".join(tf.getnames()[:80]))
                    relevant = [l for l in log.splitlines() if re.search(
                        r"gen_wall|gen_user_cpu|gen_system_cpu|wall.?time|cpu.?time|elapsed|nAccepted|All included",
                        l, re.I)]
                    evidence.extend(relevant[-30:])
                    evidence.append("TIMING_FIELDS: " + str({k: row[k] for k in ("wall_s","cpu_s","timing_source")}))
            except (OSError, ValueError, EOFError, tarfile.TarError) as exc:
                row["error"] = str(exc)
            rows.append(row)
        if len(rows) != merged["files"] or sum(r["entries"] for r in rows) != merged["entries"]:
            raise ValueError("Merge coverage mismatch " + sample)
        sw = math.fsum(r["sumW"] for r in rows)
        sw2 = math.fsum(r["sumW2"] for r in rows)
        if not (math.isclose(sw, merged["sumW"], rel_tol=1e-4) and
                math.isclose(sw2, merged["sumW2"], rel_tol=1e-4)):
            raise ValueError("Merge weight moments mismatch " + sample)
        result = dict(sample=sample, jobs=len(rows), events=merged["entries"],
                      neff=merged["neff"], xs_pb=merged["xs_pb"])
        for key in ("wall_s", "cpu_s"):
            j,n,total,per_event,per_eff = summarize(rows, key)
            result.update({key+"_jobs":j, key+"_events":n, key+"_total":total,
                           key+"_per_event":per_event, key+"_per_neff":per_eff})
        exact = [r for r in rows if r["tried"] and r["accepted"]]
        approx = [r for r in rows if r["reported_eff"]]
        result["fxfx_exact_jobs"] = len(exact)
        result["fxfx_exact"] = (sum(r["accepted"] for r in exact)/sum(r["tried"] for r in exact)
                                if exact else None)
        result["fxfx_reported_jobs"] = len(approx)
        result["fxfx_estimated"] = (sum(r["entries"] for r in approx)/
            sum(r["entries"]/r["reported_eff"] for r in approx) if approx else None)
        result["errors"] = sum(bool(r["error"]) for r in rows)
        individual.extend(rows)
        summary.append(result)
        print(sample, "jobs=", len(rows), "wall coverage=", result["wall_s_jobs"],
              "cpu coverage=", result["cpu_s_jobs"], "wall s/ev=", fmt(result["wall_s_per_event"]),
              "CPU s/ev=", fmt(result["cpu_s_per_event"]), "CPU s/Neff=", fmt(result["cpu_s_per_neff"]),
              "FxFx exact=", fmt(result["fxfx_exact"]), "FxFx approx=", fmt(result["fxfx_estimated"]),
              "errors=", result["errors"], flush=True)
    for name, rows in (("per_job.csv", individual), ("summary.csv", summary)):
        with (a.output/name).open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    (a.output/"timing_evidence.txt").write_text("\n".join(evidence)+"\n")
    print("OUTPUT="+str(a.output))
    print("Timing totals cover successful matched jobs only; partial coverage is not a full-production cost.")
    print("FxFx approximate uses target EVNT counts and reported efficiencies; exact uses Pythia counters.")


if __name__ == "__main__":
    main()
