#!/usr/bin/env python3
"""Read-only preflight for real AQP V+jets differential plots.

Inspect the eight *existing merged YODA* files, the original RAW histograms
and cross-section/event-weight metadata. Never modify, normalize, or merge
these files. A report of metadata presence is not certification of the
physical cross-section or correct HT2-bias handling.
"""
import argparse
import gzip
import json
from pathlib import Path

CONFIGS = ("standard111", "delta111", "delta221", "delta441")
FILES = {
    "Zee": {
        "standard111": "old:Zee/standard111/merged/Zee_standard111_v2_nominal_shapes.yoda.gz",
        "delta111": "old:Zee/delta111/merged/Zee_delta111_v2_nominal_shapes.yoda.gz",
        "delta221": "old:Zee/delta221/merged/Zee_delta221_v2_nominal_shapes.yoda.gz",
        "delta441": "new:Zee/delta441/v3/merged/Zee_delta441_v3_full.yoda.gz",
    },
    "Wenu": {
        "standard111": "new:Wenu/standard111/v1/merged/Wenu_standard111_v1_full.yoda.gz",
        "delta111": "old:Wenu/delta111/merged/Wenu_delta111_v2_nominal_shapes.yoda.gz",
        "delta221": "old:Wenu/delta221/merged/Wenu_delta221_v2_nominal_shapes.yoda.gz",
        "delta441": "new:Wenu/delta441/v3/merged/Wenu_delta441_v3_full.yoda.gz",
    },
}
OLD_CROSS_SECTION = {("Zee", c) for c in CONFIGS[:3]} | {
    ("Wenu", "delta111"), ("Wenu", "delta221")}
COMMON = {
    "Zee": ("MC_ZJETS", "MC_ZINC"),
    "Wenu": ("MC_WJETS", "MC_WINC"),
}
META_NAMES = ("_XSEC", "_EVTCOUNT", "_SUMW", "MC_XS", "MC_WEIGHTS")


def reference_path(process, config, old, new):
    location, relative = FILES[process][config].split(":", 1)
    return (old if location == "old" else new) / relative


def canonical(path):
    """Canonicalize only the known equivalent electron MC analysis name."""
    for name in ("MC_ZJETS", "MC_ZINC", "MC_WJETS", "MC_WINC"):
        prefix = "/" + name + ":LMODE=EL/"
        if path.startswith(prefix):
            return "/" + name + "/" + path[len(prefix):]
    return path


def scan_yoda(source):
    """Capture metadata records verbatim and check per-analysis object presence."""
    record = {
        "exists": source.is_file(), "size_bytes": None, "error": None,
        "finalized_count": 0, "raw_count": 0, "raw_histogram_count": 0,
        "analyses": {}, "canonical_final_paths": [],
        "metadata_blocks": []
    }
    if not source.is_file():
        record["error"] = "FILE_MISSING"
        return record
    record["size_bytes"] = source.stat().st_size
    if record["size_bytes"] < 100:
        record["error"] = "FILE_TOO_SHORT"
        return record

    path, kind, capture = None, None, []
    final_paths = set()
    analysis = {}
    try:
        opener = gzip.open if source.suffix == ".gz" else open
        with opener(source, "rt", encoding="utf-8", errors="replace") as fh:
            for original in fh:
                line = original.strip()
                if line.startswith("BEGIN YODA_"):
                    parts = line.split(maxsplit=2)
                    kind = parts[1] if len(parts) > 1 else ""
                    path = parts[2] if len(parts) > 2 else ""
                    capture = []
                elif line.startswith("Path: /"):
                    path = line[6:].strip()
                elif line.startswith("END YODA_"):
                    if path:
                        if path.startswith("/RAW/"):
                            record["raw_count"] += 1
                            if "HISTO" in (kind or "") or "PROFILE" in (kind or ""):
                                record["raw_histogram_count"] += 1
                        elif path.startswith("/TMP/") or path.startswith("/REF/"):
                            pass
                        else:
                            record["finalized_count"] += 1
                            canon = canonical(path)
                            final_paths.add(canon)
                            group = canon.lstrip("/").split("/", 1)[0].split(":", 1)[0]
                            analysis[group] = analysis.get(group, 0) + 1
                        if any(token in path for token in META_NAMES):
                            record["metadata_blocks"].append({
                                "path": path, "object_type": kind,
                                "sample_data_lines": capture[:8],
                            })
                    path, kind, capture = None, None, []
                elif kind and path and any(token in path for token in META_NAMES):
                    if (line and not line.startswith(("#", "Type:", "Title:",
                                                    "Path:", "ErrorLabels:",
                                                    "ScaledBy:", "---"))):
                        if len(capture) < 8:
                            capture.append(line[:240])
        if kind is not None:
            record["error"] = "TRUNCATED_YODA_BLOCK"
    except (OSError, EOFError, UnicodeError) as exc:
        record["error"] = type(exc).__name__ + ": " + str(exc)
    record["analyses"] = analysis
    record["canonical_final_paths"] = sorted(final_paths)
    if record["raw_histogram_count"] == 0 and not record["error"]:
        record["error"] = "NO_RAW_HISTOGRAMS: cannot assume safe re-finalization"
    return record


def audit(old, new):
    rows = {}
    for process in FILES:
        for config in CONFIGS:
            path = reference_path(process, config, old, new)
            row = scan_yoda(path)
            row.update({
                "process": process, "config": config,
                "input": str(path),
                "version": ("v3" if config == "delta441" else
                            "v1" if (process, config) == ("Wenu", "standard111")
                            else "v2"),
                "athena_cross_section_setting":
                    "1.0_pb_artificial" if (process, config) in OLD_CROSS_SECTION
                    else "0.0_use_hepmc_if_available",
            })
            rows[f"{process}/{config}"] = row
    overlap = {}
    for process, analyses in COMMON.items():
        for analysis in analyses:
            common = None
            sizes = {}
            for config in CONFIGS:
                row = rows[f"{process}/{config}"]
                found = {
                    p for p in row["canonical_final_paths"]
                    if p.startswith("/" + analysis + "/")
                }
                sizes[config] = len(found)
                common = found if common is None else common & found
            overlap[process + "/" + analysis] = {
                "common_finalized_histograms": len(common),
                "by_config": sizes,
            }
    return {
        "status": "AUDIT_ONLY_NOT_RATE_CERTIFIED",
        "notes": [
            "Old v2 YODA CrossSection=1 pb is artificial, not a physical rate.",
            "New v1/v3 CrossSection=0 asks Rivet to use HepMC XS if present; verify it.",
            "The generator run_card event_norm=bias means use the *actual* weights.",
            "Do not use old Wenu standard111 v2: its seed is invalid.",
            "DO NOT scale absolute rates by fitting the plots or use presentation factors.",
            "Rivet -e equivalent merging re-finalizes RAW objects; only attempt after XS audit.",
        ],
        "samples": rows, "common_plot_coverage": overlap,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--old", type=Path, default=Path("/data/aalida/AQP_Rivet"))
    p.add_argument("--new", type=Path,
                   default=Path("/data/aalida/AQP_Rivet_full/outputs"))
    p.add_argument("--out", type=Path, default=Path(
        "/data/aalida/AQP_Rivet_full/outputs/physics_preflight_20261123.json"))
    args = p.parse_args()
    report = audit(args.old, args.new)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{'sample':22} {'ver':>3} {'Rivet XS setting':>24} {'final':>6} "
          f"{'RAW':>6} {'XSEC':>5} {'SUMW':>5} {'error':>15}")
    print("-"*94)
    failures = 0
    for name, row in report["samples"].items():
        metadata = " ".join(v["path"] for v in row["metadata_blocks"])
        hasxs = any("_XSEC" in v["path"] or "/MC_XS/" in v["path"]
                    for v in row["metadata_blocks"])
        hassumw = any("_SUMW" in v["path"] or "_EVTCOUNT" in v["path"]
                      for v in row["metadata_blocks"])
        failures += bool(row["error"])
        print(f"{name:22} {row['version']:>3} "
              f"{row['athena_cross_section_setting']:>24} "
              f"{row['finalized_count']:>6} {row['raw_count']:>6} "
              f"{int(hasxs):>5} {int(hassumw):>5} {str(row['error'] or '-'):>15}")
    print("\nShared finalized MC histogram coverage:")
    for key, value in report["common_plot_coverage"].items():
        print(f"  {key}: {value['common_finalized_histograms']} common histograms; "
              f"per configuration={value['by_config']}")
    print(f"\nPHYSICS_PREFLIGHT_OUTPUT={args.out}")
    print("RATE_NORMALIZATION_VALIDATED=NO")
    if failures:
        print(f"PREFLIGHT_FILE_OR_FORMAT_ERRORS={failures}")
        return 1
    print("PREFLIGHT_INPUT_FILES_READABLE=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
