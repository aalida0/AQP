#!/usr/bin/env python3
"""Read-only AF inventory of Wenu FxFx standard111/delta111/delta221.

Does not extract or hash multi-GB archives, execute MadGraph, unpickle
job_status.pkl, or modify process trees. Run on the AF login node.
The result establishes only candidate status, NOT gridpack validation.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

CONFIGS = {"standard111": ("false", (1, 1, 1)),
           "delta111": ("true", (1, 1, 1)),
           "delta221": ("true", (2, 2, 1))}
PROC = "PROCNLO_loop_sm-no_b_mass_0"

def card_settings(path):
    vals, duplicates = {}, {}
    if not path.is_file():
        return vals, duplicates
    for line in path.read_text(errors="replace").splitlines():
        body = line.split("#", 1)[0].split("!", 1)[0].strip()
        if "=" not in body:
            continue
        value, key = body.rsplit("=", 1)
        key = key.strip().lower()
        value = value.strip().lower()
        if key in vals:
            duplicates.setdefault(key, []).append(vals[key])
        vals[key] = value
    return vals, duplicates

def cfg_audit(base, home, cfg):
    d, fold = CONFIGS[cfg]
    name = f"mc_13TeV.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_{cfg}.MG3511.GRID.tar.gz"
    tar = base / "gridpacks" / name
    copies = [base / cfg / PROC, home / cfg / PROC]
    process = next((p for p in copies if p.is_dir()), None)
    row = {
        "configuration": cfg,
        "archive": str(tar),
        "archive_exists": tar.is_file() and tar.stat().st_size > 0,
        "archive_bytes": tar.stat().st_size if tar.is_file() else None,
        "recorded_sha256_exists": Path(str(tar) + ".sha256").is_file(),
        "source_process": str(process) if process else None,
        "source_locations_searched": [str(p) for p in copies],
        "expected_mcatnlo_delta": d,
        "expected_folding": list(fold),
        "warnings": [],
        "errors": [],
    }
    if not row["archive_exists"]:
        row["errors"].append("Packaged gridpack absent")
    if not row["recorded_sha256_exists"]:
        row["warnings"].append("Packager SHA256 sidecar absent")
    if process:
        sub = process / "SubProcesses"
        req = ("job_status.pkl", "randinit", "orderstags_glob.dat")
        row["checkpoint_files"] = {
            n: (sub / n).is_file() and (sub / n).stat().st_size > 0 for n in req
        }
        for n, ok in row["checkpoint_files"].items():
            if not ok:
                row["errors"].append("Missing source state: " + n)
        gfs = [p for p in sub.glob("P*/GF*") if p.is_dir()]
        row["gf_directories"] = len(gfs)
        row["gf_nonempty_res1"] = sum((p / "res_1.dat").is_file() and
                                       (p / "res_1.dat").stat().st_size > 0 for p in gfs)
        if len(gfs) != 300 or row["gf_nonempty_res1"] != 300:
            row["errors"].append("MINT1 GF target count or res_1.dat completeness differs from 300")
        row["combined_lhe_exists"] = (
            (process / "Events/run_01/events.lhe.gz").is_file()
            and (process / "Events/run_01/events.lhe.gz").stat().st_size > 0
        )
        vals, duplicates = card_settings(process / "Cards/run_card.dat")
        keys = ("folding", "mcatnlo_delta", "ickkw", "nevents",
                "event_norm", "ptj", "jetradius", "lhaid",
                "pdlabel", "ebeam1", "ebeam2", "parton_shower",
                "req_acc", "maxjetflavor", "nevt_job")
        row["effective_run_card"] = {k: vals.get(k) for k in keys}
        row["duplicate_card_entries"] = {k: v for k, v in duplicates.items()
                                           if k in keys}
        delta = vals.get("mcatnlo_delta")
        if delta not in (d, d[0], ".true." if d == "true" else ".false."):
            row["errors"].append(f"mcatnlo_delta={delta!r}, expected {d}")
        fold_str = vals.get("folding", "")
        try:
            actual_folding = tuple(int(x) for x in re.split(r"[,\s]+", fold_str) if x)
        except ValueError:
            actual_folding = None
        if actual_folding != fold:
            row["errors"].append(f"folding={fold_str!r}, expected {fold}")
        if vals.get("ickkw") != "3":
            row["errors"].append("Expected FxFx ickkw=3")
        for k, desired in (("ebeam1", 6500), ("ebeam2", 6500)):
            try:
                if not math.isfinite(float(vals.get(k, "nan").replace("d", "e"))) or abs(float(vals.get(k, "nan").replace("d", "e"))-desired) > 1e-4:
                    row["errors"].append(f"{k} is not {desired} GeV")
            except ValueError:
                row["errors"].append(f"Bad {k}")
        if vals.get("event_norm") != "bias":
            row["warnings"].append("event_norm is not 'bias'; audit HT2 bias convention")
        if vals.get("parton_shower", "").replace("'", "").replace('"', "").lower() != "pythia8":
            row["warnings"].append("parton_shower not explicitly Pythia8")
        source_opts = process / "Source/make_opts"
        row["source_make_opts_has_libcpp"] = (
            "-lc++" in source_opts.read_text(errors="replace")
            if source_opts.is_file() else None
        )
        row["stale_top_level_debug_logs"] = [
            p.name for p in process.glob("*_debug.log") if p.is_file()
        ][:25]
        if row["source_make_opts_has_libcpp"]:
            row["warnings"].append("Archive may require -lc++ -> -lstdc++ scratch-only link fix")
        if row["stale_top_level_debug_logs"]:
            row["warnings"].append("Archived historical debug logs must be quarantined on worker")
    else:
        row["warnings"].append("Source process not found: archive needs worker-side card/checkpoint inspection")
    row["status"] = "BLOCKED" if row["errors"] else "CANDIDATE_NEEDS_WORKER_SMOKE"
    return row

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path,
                   default=Path("/data/aalida/AQP/Wjets/WENU"))
    p.add_argument("--home", type=Path,
                   default=Path("/home/aalida/AQP/Wjets/WENU"))
    args = p.parse_args()
    rows = [cfg_audit(args.data, args.home, cfg) for cfg in CONFIGS]
    for row in rows:
        print("\n" + "="*72)
        print(row["configuration"].upper(), row["status"])
        print("Archive:", row["archive"])
        print("Archive bytes:", row["archive_bytes"])
        print("SHA256 sidecar:", row["recorded_sha256_exists"])
        print("Source process:", row["source_process"])
        print("GF targets/results:", row.get("gf_directories"),
              "/", row.get("gf_nonempty_res1"))
        print("Checkpoint:", row.get("checkpoint_files", "not inspected"))
        print("Card:", row.get("effective_run_card", "not inspected"))
        print("Historical debug logs:", row.get("stale_top_level_debug_logs"))
        print("Source make_opts contains -lc++:", row.get("source_make_opts_has_libcpp"))
        for msg in row["errors"]:
            print("ERROR:", msg)
        for msg in row["warnings"]:
            print("NOTE:", msg)
    print("\nAQP_WENU_ARCHIVE_INVENTORY_JSON_BEGIN")
    print(json.dumps(rows, indent=2))
    print("AQP_WENU_ARCHIVE_INVENTORY_JSON_END")
    print("\nNo generator code executed. No source or gridpack data modified.")
    if any(row["status"] == "BLOCKED" for row in rows):
        print("AQP_WENU_ARCHIVE_INVENTORY_CONTAINS_BLOCKERS")
    else:
        print("AQP_WENU_ARCHIVE_INVENTORY_CANDIDATES_ONLY_NOT_VALIDATED")
    return 0

if __name__ == "__main__":
    sys.exit(main())
