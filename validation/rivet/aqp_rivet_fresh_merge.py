#!/usr/bin/env python3
"""Merge only fresh, manifest-matched YODA with physical per-job XS."""
import argparse
import json
import math
from pathlib import Path
import subprocess
import tempfile

from aqp_vjets_physics_preflight import scan_yoda
from aqp_vjets_xsec_per_file import get_first

OUT = Path("/data/aalida/AQP_Rivet_full/outputs/fresh_rivet_20261124")


def input_path(sample, row):
    return OUT/"full"/sample/"yoda"/row["evnt"].replace(".EVNT.pool.root", ".yoda.gz")


# Both registered WebDAV sources failed on AF; keep the frozen manifest intact.
UNAVAILABLE = ("Zee/delta221/v2", "user.aalida.53564254._000060.EVNT.pool.root")


def select_inputs(sample, data):
    selected, excluded = [], []
    for r in data["included"]:
        path = input_path(sample, r)
        if ((sample, r["evnt"]) == UNAVAILABLE and
                not path.exists() and not path.with_suffix(".json").exists()):
            excluded.append({**r, "reason": "WEBDAV_TRANSFER_UNAVAILABLE"})
            print(f"ALLOWED_MISSING {sample} {r['evnt']} entries={r['entries']}", flush=True)
        else:
            selected.append(r)
    return selected, excluded


def coverage(sample, data):
    selected, excluded = select_inputs(sample, data)
    paths = [input_path(sample, r) for r in selected]
    if len(set(paths)) != len(paths):
        raise ValueError("Duplicate manifest input")
    missing = [p for p in paths if not p.is_file() or not p.with_suffix(".json").is_file()]
    print(f"COVERAGE {sample} {len(paths)-len(missing)}/{len(data['included'])} "
          f"planned_events={sum(r['entries'] for r in data['included'])} "
          f"allowed_missing={len(excluded)} "
          f"manifest_excluded={len(data['excluded'])}", flush=True)
    for p in missing:
        print(f"MISSING {p}")
    return not missing and bool(paths)


def metadata(path):
    m = scan_yoda(path)
    if m["error"]:
        raise ValueError(f"{path}: {m['error']}")
    xs = get_first(m, "_XSEC")
    ev = next(b["sample_data_lines"][0] for b in m["metadata_blocks"]
              if b["path"] == "/RAW/_EVTCOUNT")
    sw, sw2, n = map(float, ev.split()[:3])
    if not all(math.isfinite(x) for x in (xs, sw, sw2, n)) or xs <= 0 or sw2 <= 0 or n <= 0:
        raise ValueError(f"Invalid metadata {path}")
    return xs, sw, sw2, n, m


def combine(rows):
    sw = math.fsum(r[1] for r in rows)
    sw2 = math.fsum(r[2] for r in rows)
    n = math.fsum(r[3] for r in rows)
    trials = math.fsum(r[1]/r[0] for r in rows)
    if sw <= 0 or trials <= 0:
        raise ValueError("Nonpositive combined signed weight or trial normalization")
    return sw/trials, sw, sw2, n


def merge(sample, data):
    if not coverage(sample, data):
        raise ValueError("Incomplete manifest coverage")
    selected, transfer_excluded = select_inputs(sample, data)
    inputs, rows = [], []
    analyses = None
    for r in selected:
        path = input_path(sample, r)
        receipt = json.loads(path.with_suffix(".json").read_text())
        xs, sw, sw2, n, m = metadata(path)
        if (receipt["evnt"] != r["evnt"] or receipt["sample"] != sample or
                receipt["dataset"] != data["dataset"] or n != r["entries"] or
                receipt["entries"] != n or
                not math.isclose(xs, r["xs"]["xs_pb"], rel_tol=1e-4) or
                not math.isclose(sw, receipt["sumW"], rel_tol=1e-6) or
                not math.isclose(sw2, receipt["sumW2"], rel_tol=1e-6)):
            raise ValueError(f"Manifest/receipt/YODA mismatch: {path}")
        found = set(m["analyses"])
        if not {"MC_XS", "MC_WEIGHTS"} <= found:
            raise ValueError(f"Missing weight or XS analysis: {path}")
        if analyses is None:
            analyses = found
        elif found != analyses:
            raise ValueError(f"Inconsistent analysis suite: {path}")
        inputs.append(str(path))
        rows.append((xs, sw, sw2, n))
    xs, sw, sw2, n = combine(rows)
    print(f"EXPECTED {sample} XS_PB={xs:.10g} SUMW={sw:.10g} SUMW2={sw2:.10g} ENTRIES={n:g}", flush=True)
    folder = OUT/"merged"
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder/(sample.replace("/", "_")+"_fresh.yoda.gz")
    report = dest.with_suffix(".json")
    if dest.exists() or report.exists():
        raise FileExistsError(f"Refusing to overwrite {dest} or {report}")
    with tempfile.TemporaryDirectory(dir=folder, prefix=".merge-") as tmp:
        out = Path(tmp)/dest.name
        subprocess.run(["rivet-merge", "-e", "-o", str(out), *inputs], check=True)
        gx, gw, gw2, gn, m = metadata(out)
        print(f"ACTUAL {sample} XS_PB={gx:.10g} SUMW={gw:.10g} SUMW2={gw2:.10g} ENTRIES={gn:g}", flush=True)
        if not (math.isclose(gx, xs, rel_tol=5e-4) and
                math.isclose(gw, sw, rel_tol=1e-4) and
                math.isclose(gw2, sw2, rel_tol=1e-4) and gn == n and
                analyses <= set(m["analyses"])):
            raise ValueError("Merged metadata or analysis coverage mismatch")
        records = {b["path"]: b["sample_data_lines"] for b in m["metadata_blocks"]
                   if b["path"].startswith("/MC_XS/")}
        if not all(records.get("/MC_XS/"+k) for k in ("XS", "N", "pmXS", "pmN")):
            raise ValueError("Missing finalized MC_XS records")
        result = {"sample": sample, "files": len(inputs), "entries": gn,
                  "xs_pb": gx, "sumW": gw, "sumW2": gw2,
                  "neff": gw*gw/gw2, "neff_over_n": gw*gw/(gw2*gn),
                  "excluded": data["excluded"] + transfer_excluded, "mc_xs_records": records,
                  "analyses": m["analyses"], "metadata_check": "PASS",
                  "physics_validated": False}
        out.replace(dest)
        with report.open("x") as f:
            json.dump(result, f, indent=2)
    print(f"FRESH_MERGE_PASS={dest} NEFF={result['neff']:.8g} NEFF_OVER_N={result['neff_over_n']:.8g}", flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sample")
    a = p.parse_args()
    samples = json.loads((OUT/"production_manifest.json").read_text())["samples"]
    if a.sample:
        merge(a.sample, samples[a.sample])
        return 0
    checks = [coverage(s, d) for s, d in samples.items()]
    print("FRESH_COVERAGE=" + ("PASS" if all(checks) else "FAIL"))
    return int(not all(checks))


if __name__ == "__main__":
    raise SystemExit(main())
