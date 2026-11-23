#!/usr/bin/env python3
"""Non-destructive, validated remerge of Wenu D441 v3, excluding two -1 pb XS jobs.

READS: complete 1984-file audit JSON and 1982 original per-file Rivet YODA.
WRITES: new directory only; original merged YODA and per-file files unchanged.
Default is dry-run. --execute calls rivet-merge -e on full 1982-file whitelist,
and validates XS, signed weight sum, and event count afterward.

The ~21.1 nb XS is provisional pending comparison to independent generator logs.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

from aqp_vjets_physics_preflight import scan_yoda
from aqp_vjets_xsec_per_file import get_first

EXPECTED_BAD_NAMES = {
    "user.aalida.53651999._001393_282ffe59518d.yoda.gz",
    "user.aalida.53651999._001701_90b7be0871e6.yoda.gz",
}
DEFAULT_JSON = Path(
    "/data/aalida/AQP_Rivet_full/outputs/wenu_d441_xsec_full_20261123.json")
DEFAULT_DIR = Path(
    "/data/aalida/AQP_Rivet_full/outputs/"
    "physics_remerge_Wenu_D441_validXS_20261123")


def load_audit(json_path):
    audit = json.loads(json_path.read_text(encoding="utf-8"))
    rows = audit["per_file"]
    stats = audit["summary"]
    if len(stats) != 1 or (stats[0]["process"], stats[0]["config"]) != (
            "Wenu", "delta441"):
        raise ValueError("Expected Wenu/delta441-only all-files JSON")
    if len(rows) != 1984 or stats[0]["n_files_checked"] != 1984:
        raise ValueError("Expected complete 1,984-file audit; refusing partial input")

    keep, bad = [], []
    for row in rows:
        if (row["process"], row["config"]) != ("Wenu", "delta441"):
            raise ValueError("Mixed configurations present")
        source = Path(row["source"])
        if not str(source).startswith(
            "/data/aalida/AQP_Rivet_full/outputs/Wenu/delta441/v3/yoda/"
        ):
            raise ValueError("Unexpected source folder " + str(source))
        if row.get("error") is not None:
            raise ValueError("Unreadable YODA in input " + str(source))
        xs, sw = row.get("xsec_pb"), row.get("sumW")
        if not (isinstance(xs, (float, int)) and isinstance(sw, (float, int))
                and math.isfinite(xs) and math.isfinite(sw)):
            raise ValueError("Missing or nonfinite XS/sumW in " + str(source))
        if xs <= 0 or sw <= 0:
            bad.append(row)
        else:
            if row.get("entries") != 1000:
                raise ValueError("Unexpected events per file " + str(source))
            keep.append(row)

    if len(keep) != 1982 or len(bad) != 2:
        raise ValueError("Unexpected number of kept/rejected YODA files")
    if {Path(row["source"]).name for row in bad} != EXPECTED_BAD_NAMES:
        raise ValueError("Bad-file set changed; aborting rather than silently excluding")
    if any(row["xsec_pb"] != -1.0 for row in bad):
        raise ValueError("Excluded-file cross sections not exactly -1 pb")

    paths = [Path(r["source"]) for r in keep]
    if len(set(map(str,paths))) != len(paths):
        raise ValueError("Duplicate input paths")
    if any(not path.is_file() for path in paths):
        missing = [str(p) for p in paths if not p.is_file()]
        raise ValueError("Missing source files: " + ", ".join(missing[:5]))

    # First reconstruct the already observed defective merge from all 1984
    # records. It must agree with Rivet metadata before filtering the -1 pb
    # sentinel cross sections: otherwise abort rather than guessing.
    all_signed = sum(r["sumW"] for r in rows)
    all_denominator = sum(r["sumW"]/r["xsec_pb"] for r in rows)
    reconstructed_original = all_signed/all_denominator
    merged_original = stats[0].get("merged_xsec_pb")
    if (merged_original is None or
            abs(reconstructed_original/merged_original - 1) > 0.0005):
        raise ValueError("Could not reproduce original merged cross section")

    signed = sum(r["sumW"] for r in keep)
    denominator = sum(r["sumW"]/r["xsec_pb"] for r in keep)
    if denominator <= 0 or signed <= 0:
        raise ValueError("Invalid predicted equivalent merge normalization")
    prediction = signed/denominator

    if not (18000 < prediction < 28000):
        raise ValueError(f"Predicted XS {prediction} outside pilot sanity interval")
    return paths, bad, {
        "status": "PROVISIONAL_WENU_D441_VALID_XS_REMERGE_NOT_RATE_CERTIFIED",
        "source_json": str(json_path),
        "included_yoda": len(keep), "excluded_yoda": len(bad),
        "included_entries": sum(int(r["entries"]) for r in keep),
        "expected_sumW": signed, "predicted_rivet_equiv_xsec_pb": prediction,
        "reconstructed_old_xsec_pb": reconstructed_original,
        "observed_old_xsec_pb": merged_original,
        "excluded_sources": bad,
        "physics_note": (
            "Two anomalous -1 pb cross-section records excluded. "
            "Not a standalone certification of physical generator XS."),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", type=Path, default=DEFAULT_JSON)
    p.add_argument("--outdir", type=Path, default=DEFAULT_DIR)
    p.add_argument("--logdir", type=Path, default=Path.cwd(),
                   help="rivet-merge process logs (default: current Condor scratch directory, NOT /data)")
    p.add_argument("--execute", action="store_true", help="actually run rivet-merge")
    args = p.parse_args()

    paths, excluded, manifest = load_audit(args.json.expanduser())
    outdir = args.outdir.expanduser().absolute()
    # Deliberately keep all output outside the original per-file and merged tree.
    original_root = Path(
        "/data/aalida/AQP_Rivet_full/outputs/Wenu/delta441/v3").resolve()
    if outdir.resolve() == original_root or original_root in outdir.resolve().parents:
        p.error("Output must not be inside the original input tree")
    output = outdir / "Wenu_delta441_v3_exclude_invalidXS.yoda.gz"
    kept_list = outdir / "included_yoda_files.txt"
    excluded_file = outdir / "excluded_invalid_xs.json"
    manifest_file = outdir / "manifest.json"

    manifest.update({
        "output": str(output),
        "source_path_list_sha256": hashlib.sha256(
            "\n".join(map(str, paths)).encode()).hexdigest(),
        "method": "rivet-merge -e on unmodified original valid-XSEC YODA",
        "remerge_executed": bool(args.execute),
    })
    print(f"SELECTED={len(paths)} EXCLUDED={len(excluded)} "
          f"EXPECTED_ENTRIES={manifest['included_entries']}")
    print(f"EXPECTED_SUMW={manifest['expected_sumW']:.9g}")
    print(f"EXPECTED_XSEC_PB={manifest['predicted_rivet_equiv_xsec_pb']:.9f}")
    print(f"OUTPUT={output}")

    if not args.execute:
        print("DRY_RUN_ONLY=YES (pass --execute to perform actual merge)")
        return 0

    if not shutil.which("rivet-merge"):
        p.error("rivet-merge missing; source matching Rivet 4.1.2 LCG view")
    if output.exists():
        p.error(f"Output already exists, refusing overwrite: {output}")

    outdir.mkdir(parents=True, exist_ok=True)
    kept_list.write_text("\n".join(map(str, paths))+"\n", encoding="utf-8")
    excluded_file.write_text(json.dumps(excluded, indent=2)+"\n", encoding="utf-8")
    manifest_file.write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")

    command = ["rivet-merge", "-e", "-o", str(output), *(str(p) for p in paths)]
    print("RUNNING_RIVET_MERGE=YES", flush=True)
    print(f"RIVET_COMMAND_FILE={kept_list}", flush=True)
    logdir = args.logdir.expanduser().absolute()
    # Never place runtime log streams on the Ceph /data filesystem.
    if logdir == Path("/data") or Path("/data") in logdir.parents:
        p.error("Logging to Ceph /data is forbidden; use Condor scratch or /home")
    logdir.mkdir(parents=True, exist_ok=True)
    stdout_path = logdir / "merge.stdout.log"
    stderr_path = logdir / "merge.stderr.log"
    print(f"RIVET_PROCESS_LOGS={stdout_path} {stderr_path}", flush=True)
    with stdout_path.open("w") as stdout, stderr_path.open("w") as stderr:
        result = subprocess.run(command, stdout=stdout, stderr=stderr, check=False)
    if result.returncode != 0:
        print(f"MERGE_FAILED={result.returncode}", file=sys.stderr)
        print(f"INSPECT={stderr_path}", file=sys.stderr)
        return result.returncode

    metadata = scan_yoda(output)
    xs = get_first(metadata, "_XSEC")
    sw = get_first(metadata, "_EVTCOUNT")
    counter = next((o["sample_data_lines"][0]
                    for o in metadata["metadata_blocks"]
                    if o["path"] == "/RAW/_EVTCOUNT" and o["sample_data_lines"]),
                   None)
    entries = float(counter.split()[2]) if counter and len(counter.split()) >= 3 else None
    manifest.update({
        "actual_xsec_pb": xs, "actual_sumW": sw, "actual_entries": entries,
        "output_error": metadata["error"],
        "remerge_xs_matches_prediction": (
            xs is not None and abs(xs/manifest["predicted_rivet_equiv_xsec_pb"]-1) < 0.005),
        "sumW_matches_prediction": (
            sw is not None and abs(sw/manifest["expected_sumW"]-1) < 0.00001),
        "entries_match_expected": (entries == manifest["included_entries"]),
    })
    manifest["status"] = (
        "REMERGE_VALIDATED_METADATA_ONLY_NOT_PHYSICS_CERTIFIED"
        if all((manifest["remerge_xs_matches_prediction"],
                manifest["sumW_matches_prediction"],
                manifest["entries_match_expected"], metadata["error"] is None))
        else "REMERGE_VALIDATION_FAILED"
    )
    manifest_file.write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    print(f"ACTUAL_XSEC_PB={xs} ACTUAL_SUMW={sw} ACTUAL_ENTRIES={entries}")
    print(f"MERGE_STATUS={manifest['status']}")
    print(f"MANIFEST={manifest_file}")
    return 0 if manifest["status"].startswith("REMERGE_VALIDATED_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
