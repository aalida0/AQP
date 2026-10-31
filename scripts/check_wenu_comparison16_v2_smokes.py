#!/usr/bin/env python3
"""Read-only gate: all three fresh-gridpack 1k-LHE -> 200 EVNT smokes must pass.

Does NOT submit jobs, read old original LHE archives, or run MadGraph.
"""
import json
from pathlib import Path
import sys

BASE = Path("/data/aalida/AQP/Wjets/WENU/production_pilot/wenu_compare/smoke16_1k")
CASES = {"standard111": 311, "delta111": 321, "delta221": 322}

def check(config, seed):
    ldir = BASE / f"{config}_seed{seed}_lhe"
    sdir = BASE / f"{config}_seed{seed}_fxfx"
    for directory in (ldir, sdir):
        if not directory.is_dir():
            raise ValueError(f"missing output: {directory}")
        rc = directory / "runner_exit_code"
        if not rc.is_file() or rc.read_text().strip() != "0":
            raise ValueError(f"job not completed with exit 0: {rc}")
    audit = ldir / "lhe_weight_audit.json"
    if not audit.is_file():
        raise ValueError(f"missing LHE weight audit: {audit}")
    weights = json.loads(audit.read_text())
    if weights.get("status") != "PASS" or weights.get("num_events") != 1000:
        raise ValueError(f"no successful 1000-LHE audit: {audit}")
    if not (ldir / "validated_LHE.events").is_file():
        raise ValueError(f"no saved verified LHE file: {ldir}")
    lhe_log = (ldir / "log.generate").read_text(errors="replace")
    for x in (f"AQP_WENU_CONFIG={config}",
              "AQP_WENU_EXISTING_GRIDPACK_ONLY",
              "AQP_WENU_LHE_EVENTS_REQUESTED=1000",
              "AQP_WENU_PARALLEL_CONFIG_VERIFIED_MODE=2_NB_CORE=16"):
        if x not in lhe_log:
            raise ValueError(f"{config}: missing generation log marker {x!r}")
    shower_log = (sdir / "log.generate").read_text(errors="replace")
    for x in (f"AQP_WENU_SHOWER_CONFIG={config}",
              "AQP_FXFX_SHOWER_MADGRAPH_NOT_INVOKED",
              "Adding user hook JetMatchingMadgraph",
              "Number of events processed:"):
        if x not in shower_log:
            raise ValueError(f"{config}: missing shower marker {x!r}")
    evnt = sdir / f"wenu_{config}_seed{seed}_200evnt.EVNT.pool.root"
    if not evnt.is_file() or evnt.stat().st_size <= 0:
        raise ValueError(f"missing or empty shower EVNT: {evnt}")
    if "Number of events processed:" not in shower_log or not any(
        line.strip().endswith("200") and "Number of events processed:" in line
        for line in shower_log.splitlines()
    ):
        raise ValueError(f"{config}: no exact 200-event processing confirmation")
    print(f"AQP_WENU_COMPARE16_V2_SMOKE_PASS {config}: LHE=1000, EVNT=200")


def main():
    try:
        for config, seed in CASES.items():
            check(config, seed)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("AQP_WENU_COMPARE16_V2_SMOKE_GATE_FAIL:", exc, file=sys.stderr)
        return 1
    print("AQP_WENU_COMPARE16_V2_ALL_THREE_SMOKE_GATES_PASS")
    print("Pilot submission is now eligible if no pilot jobs have been submitted")
    print("and no pilot output directories exist:")
    print("  condor_submit_dag .aqp_staged/wenu_compare16_v2/pilot25k.dag")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
