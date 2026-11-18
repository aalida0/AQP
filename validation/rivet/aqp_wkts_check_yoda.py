#!/usr/bin/env python3
"""Check that the AQP W+jets kT smoke YODA contains populated histograms.

This is an output sanity check, not a certificate of physics equivalence.
Run with the Rivet/YODA Python environment provided by AthGeneration.
"""
import argparse
import math
from pathlib import Path


def inspect(objects, prefix="/AQP_WKTSPLITTINGS"):
    rows = []
    for path, hist in sorted(objects.items()):
        if prefix not in path or path.startswith("/RAW/") or not (
            hasattr(hist, "numEntries") and hasattr(hist, "sumW")
        ):
            continue
        entries = float(hist.numEntries())
        sumw = float(hist.sumW())
        if not math.isfinite(entries) or not math.isfinite(sumw):
            raise ValueError(f"Nonfinite histogram statistics: {path}")
        rows.append((path, entries, sumw))
    if not rows:
        raise ValueError("No AQP_WKTSPLITTINGS histograms found")
    if not any(entries > 0 for _, entries, _ in rows):
        raise ValueError("No populated AQP_WKTSPLITTINGS histograms")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("yoda", type=Path)
    args = parser.parse_args()
    if not args.yoda.is_file():
        parser.error(f"YODA file not found: {args.yoda}")
    try:
        import yoda
    except ImportError as exc:
        parser.error(f"YODA Python module unavailable: {exc}; use AthGeneration/YODA environment")
    try:
        rows = inspect(yoda.read(str(args.yoda)))
    except (ValueError, RuntimeError, OSError) as exc:
        parser.error(str(exc))
    for path, entries, sumw in rows:
        print(f"HIST {path} entries={entries:g} sumW={sumw:.9g}")
    print(f"AQP_WKTS_YODA_POPULATED_PASS={len(rows)}")
    print("NOTE: This does NOT validate absolute normalization or physics equivalence.")


if __name__ == "__main__":
    main()
