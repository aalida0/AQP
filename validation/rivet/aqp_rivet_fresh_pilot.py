#!/usr/bin/env python3
"""One-file fresh EVNT pilot per valid production; never reads old YODA."""
import argparse
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from aqp_rivet_stream import listed_files
from aqp_vjets_generator_xsec_evidence import PLAN, decode_log, log_paths
from aqp_vjets_v2_xsec_match import extract_xsec, job_key
from aqp_vjets_physics_preflight import scan_yoda
from aqp_vjets_xsec_per_file import get_first

ROOT = Path("/data/aalida/AQP_Rivet_full")
LOGS = Path("/data/aalida/AQP/aqp_log_comparison")
ROUTINES = {
    "Zee": ("MC_ZJETS:LMODE=EL", "MC_ZINC:LMODE=EL", "MC_KTSPLITTINGS",
            "MC_ZKTSPLITTINGS:LMODE=EL", "MC_WEIGHTS", "MC_XS",
            "ATLAS_2017_I1514251:LMODE=EL", "CMS_2018_I1667854:LMODE=EL",
            "ATLAS_2022_I2077570:LMODE=ELEL"),
    "Wenu": ("MC_WJETS:LMODE=EL", "MC_WINC:LMODE=EL", "MC_KTSPLITTINGS",
             "MC_WEIGHTS", "MC_XS", "ATLAS_2024_I2765017:MODE=FIDUCIAL:TYPE=SM"),
}


def choose_pair(entries, paths):
    by_id = {}
    for path in paths:
        key = job_key(path)
        if key is None:
            continue
        if key in by_id:
            raise ValueError(f"Ambiguous generator log for {key}")
        info, error = extract_xsec(decode_log(path))
        if not error and info is not None:
            by_id[key] = (path, info)
    for name, registered in sorted(entries):
        if job_key(name) in by_id:
            path, info = by_id[job_key(name)]
            return name, registered, path, info
    raise ValueError("No EVNT file with a valid matching generator log")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("process", choices=ROUTINES)
    p.add_argument("config", choices=("standard111", "delta111", "delta221", "delta441"))
    p.add_argument("version", choices=("v1", "v2", "v3"))
    a = p.parse_args()
    proc, cfg, ver = a.process, a.config, a.version
    if (proc, cfg, ver) not in PLAN:
        p.error("Incorrect production version for this sample")
    ds = f"user.aalida:user.aalida.AQP.{proc}.{cfg}.FxFx2M.{ver}_EVNT.pool.root"
    entries = listed_files(ds)
    name, registered, log, info = choose_pair(entries, log_paths(LOGS/proc/cfg/ver))
    xs = info["xs_pb"]
    outdir = ROOT/"outputs/fresh_rivet_20261124"/"pilot"/proc/cfg/ver
    outdir.mkdir(parents=True, exist_ok=True)
    dest = outdir/(name.removesuffix(".EVNT.pool.root") + ".yoda.gz")
    if dest.exists():
        p.error(f"Refusing to overwrite {dest}")
    print(f"FRESH_PILOT={proc}/{cfg}/{ver} EVNT={name} LOG={log} XS_PB={xs}", flush=True)
    local = ROOT/"inputs"/proc/cfg
    candidates = sorted(local.rglob(name)) if local.is_dir() else []
    jo = Path(__file__).resolve().with_name("aqp_rivet_fresh_evnt_job.py")
    # Use unique Condor scratch for all Athena temporary files and downloads.
    with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmp:
        work = Path(tmp)
        if candidates:
            inp = candidates[0]
        else:
            subprocess.run(["rucio", "download", "--no-subdir", "--dir", str(work),
                            "user.aalida:"+name], check=True)
            inp = work/name
        env = dict(os.environ, AQP_RIVET_INPUT=str(inp.resolve()),
                   AQP_RIVET_OUTPUT=str(work/"fresh.yoda.gz"),
                   AQP_RIVET_ANALYSES=",".join(ROUTINES[proc]),
                   AQP_RIVET_XSEC_PB=str(xs))
        subprocess.run(["athena.py", str(jo)], env=env, cwd=work, check=True)
        output = work/"fresh.yoda.gz"
        meta = scan_yoda(output)
        if meta["error"]:
            raise ValueError(meta["error"])
        got = get_first(meta, "_XSEC")
        if got is None or not math.isclose(xs, got, rel_tol=1e-4):
            raise ValueError(f"XS override failed: requested {xs}, got {got}")
        count = next(b["sample_data_lines"][0] for b in meta["metadata_blocks"]
                     if b["path"] == "/RAW/_EVTCOUNT")
        sw, sw2, n = map(float, count.split()[:3])
        if not all(math.isfinite(x) for x in (sw, sw2, n)) or sw2 <= 0 or n <= 0:
            raise ValueError("Invalid event-weight moments")
        if registered and n != registered:
            raise ValueError(f"EVNT event count mismatch: {n} vs {registered}")
        for routine in ROUTINES[proc]:
            base = routine.split(":")[0]
            if not meta["analyses"].get(base):
                raise ValueError("Missing finalized analysis " + routine)
        # Print official MC_XS records separately: the event XS recorded by that
        # routine need not be identical to the explicit AnalysisHandler override.
        for b in meta["metadata_blocks"]:
            if b["path"].startswith("/MC_XS/"):
                print("MC_XS_RECORD", b["path"], b["sample_data_lines"])
        result = {"sample": f"{proc}/{cfg}/{ver}", "dataset": ds, "evnt": name,
                  "generator_log": str(log), "expected_xs_pb": xs, "actual_xs_pb": got,
                  "sumW": sw, "sumW2": sw2, "entries": n, "neff_over_n": sw*sw/(n*sw2),
                  "analyses": meta["analyses"], "nominal_only": True}
        with dest.open("xb") as f, output.open("rb") as src:
            shutil.copyfileobj(src, f)
        dest.with_suffix(".json").write_text(json.dumps(result, indent=2)+"\n")
    print(f"FRESH_PILOT_PASS={dest} XS_PB={got} ENTRIES={n:g} NEFF_OVER_N={result['neff_over_n']:.6g}")
    print("PHYSICAL_XSEC_VALIDATED=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
