#!/usr/bin/env python3
"""Read-only eight-sample cross-section and Rivet-histogram preflight.

The physical cross section is NOT certified by this metadata check.
Use only corrected v2 output, corrected Wenu S111 v1 and remerged D441 v3.
"""
import argparse
import gzip
import json
import math
from pathlib import Path

from aqp_vjets_physics_preflight import canonical, scan_yoda
from aqp_vjets_xsec_per_file import get_first

ROOT = Path("/data/aalida/AQP_Rivet_full/outputs")
V2 = ROOT / "v2_physical_xsec_20261124"
SAMPLES = {
    "Zee": {
        "S111": V2 / "Zee_standard111_v2_full.yoda.gz",
        "D111": V2 / "Zee_delta111_v2_full.yoda.gz",
        "D221": V2 / "Zee_delta221_v2_full.yoda.gz",
        "D441": ROOT / "Zee/delta441/v3/merged/Zee_delta441_v3_full.yoda.gz",
    },
    "Wenu": {
        "S111": ROOT / "Wenu/standard111/v1/merged/Wenu_standard111_v1_full.yoda.gz",
        "D111": V2 / "Wenu_delta111_v2_full.yoda.gz",
        "D221": V2 / "Wenu_delta221_v2_full.yoda.gz",
        "D441": ROOT / "physics_remerge_Wenu_D441_validXS_20261123/Wenu_delta441_v3_exclude_invalidXS.yoda.gz",
    },
}
ANALYSES = {"Zee": ("MC_ZJETS", "MC_ZINC"),
            "Wenu": ("MC_WJETS", "MC_WINC")}


def exact_final_paths(path):
    """Read original YODA object identifiers without LMODE alias rewriting."""
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as stream:
        return {fields[2] for line in stream
                if line.startswith("BEGIN YODA_")
                for fields in (line.strip().split(maxsplit=2),)
                if len(fields) == 3
                and not fields[2].startswith(("/RAW/", "/TMP/", "/REF/"))}


def electron_paths(paths, analysis):
    """Only the explicit electron option is equivalent to the default here."""
    raw = {p for p in paths
           if p.startswith("/" + analysis + "/") or
           p.startswith("/" + analysis + ":")}
    unsupported = {p for p in raw if not
                   (p.startswith("/" + analysis + "/") or
                    p.startswith("/" + analysis + ":LMODE=EL/"))}
    if unsupported:
        raise ValueError(f"{analysis}: unsupported analysis options: {sorted(unsupported)[:2]}")
    return raw, {canonical(p) for p in raw}


def audit():
    rows, overlaps, failures = [], {}, []
    for process, samples in SAMPLES.items():
        exact_groups = {name: [] for name in ANALYSES[process]}
        canon_groups = {name: [] for name in ANALYSES[process]}
        for config, path in samples.items():
            meta = scan_yoda(path)
            xsec = get_first(meta, "_XSEC")
            count = next((v["sample_data_lines"][0]
                          for v in meta["metadata_blocks"]
                          if v["path"] == "/RAW/_EVTCOUNT"
                          and v["sample_data_lines"]), None)
            sw = nev = None
            if count:
                try:
                    cols = count.split()
                    sw, nev = float(cols[0]), float(cols[2])
                except (IndexError, ValueError):
                    pass
            good = (meta["error"] is None and
                    xsec is not None and math.isfinite(xsec) and xsec > 0 and
                    sw is not None and math.isfinite(sw) and sw > 0 and
                    nev is not None and math.isfinite(nev) and nev > 0 and
                    meta["raw_histogram_count"] > 0)
            if not good:
                failures.append(f"{process}/{config}: invalid metadata: {meta['error']}, XS={xsec}, sumW={sw}, entries={nev}")
            paths = set(meta["canonical_final_paths"])
            raw_paths = exact_final_paths(path) if meta["error"] is None else set()
            for analysis in ANALYSES[process]:
                try:
                    exact, normalized = electron_paths(raw_paths, analysis)
                    expected = {x for x in paths if x.startswith("/" + analysis + "/")}
                    if normalized != expected:
                        failures.append(f"{process}/{config}/{analysis}: canonical path mismatch")
                except ValueError as exc:
                    failures.append(f"{process}/{config}: {exc}")
                    exact, normalized = set(), set()
                exact_groups[analysis].append(exact)
                canon_groups[analysis].append(normalized)
            rows.append({"sample": f"{process}/{config}", "path": str(path),
                         "xsec_pb": xsec, "sumW": sw, "entries": nev,
                         "finalized": meta["finalized_count"],
                         "raw_histograms": meta["raw_histogram_count"],
                         "error": meta["error"]})
        for analysis in ANALYSES[process]:
            common = set.intersection(*canon_groups[analysis])
            exact = set.intersection(*exact_groups[analysis])
            overlaps[f"{process}/{analysis}"] = {"canonical": len(common), "exact": len(exact)}
            if not common:
                failures.append(f"{process}/{analysis}: no common electron-mode histograms")
            elif not exact:
                print(f"EXPECTED_ALIAS {process}/{analysis}: bare analysis name vs LMODE=EL")
        xs = [r["xsec_pb"] for r in rows if r["sample"].startswith(process + "/")]
        if len(xs) == 4 and all(isinstance(x, (float, int)) and x > 0 for x in xs):
            spread = max(xs)/min(xs) - 1
            print(f"PROCESS={process} XS_MAX_MIN_SPREAD={spread:.4%} (descriptive, not a physics tolerance test)")
    for r in rows:
        print(f'{r["sample"]:12} XS_pb={r["xsec_pb"]} EVENTS={r["entries"]} RAW={r["raw_histograms"]} ERROR={r["error"]}')
    for group, count in overlaps.items():
        print(f"COMMON_HISTOGRAMS {group} canonical={count['canonical']} exact={count['exact']}")
    for failure in failures:
        print("FAIL:", failure)
    print("EIGHT_FILE_PREFLIGHT=" + ("PASS" if not failures else "FAIL"))
    print("PHYSICAL_XSEC_VALIDATED=NO")
    return rows, overlaps, failures


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report", type=Path,
                   default=Path.home() / "AQP/vjets_8sample_absolute_preflight.json")
    a = p.parse_args()
    rows, overlaps, failures = audit()
    a.report.expanduser().parent.mkdir(parents=True, exist_ok=True)
    a.report.expanduser().write_text(
        json.dumps({"rows": rows, "overlaps": overlaps,
                    "failures": failures,
                    "physics_certified": False}, indent=2) + "\n")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
