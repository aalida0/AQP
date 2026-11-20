#!/usr/bin/env python3
"""Sanity-check populated AQP W kT splitting histograms in YODA ASCII or gzip.

Reads YODA1 *_V2 and YODA2 *_V3 histogram records without Python bindings.
This is a smoke check, not a physics-equivalence or normalization test.
"""
import argparse
import gzip
import math
import re
from pathlib import Path

ANALYSIS_PATH = re.compile(r"^/(?:RAW/)?AQP_WKTSPLITTINGS(?::[^/]*)?/")


def inspect(lines):
    """Return (path, populated_bins, entries, sumw) for matching histograms."""
    records = []
    current_type = None
    current_path = ""
    columns = None
    filled_bins = 0
    entries = 0.0
    sumw = 0.0

    def finish():
        if current_type and ANALYSIS_PATH.match(current_path):
            if columns is None:
                raise ValueError(f"Unknown histogram column format: {current_path}")
            records.append((current_path, filled_bins, entries, sumw))

    for raw in lines:
        line = raw.strip()
        if line.startswith("BEGIN YODA_"):
            if current_type is not None:
                raise ValueError("Nested YODA BEGIN without END")
            parts = line.split(maxsplit=2)
            current_type = parts[1] if ("HISTO" in parts[1] or "PROFILE" in parts[1]) else ""
            current_path = parts[2] if len(parts) > 2 else ""
            columns = None
            filled_bins = 0
            entries = sumw = 0.0
            continue
        if line.startswith("END YODA_"):
            finish()
            current_type = None
            continue
        if not current_type:
            continue
        if line.startswith("Path:"):
            current_path = line.partition(":")[2].strip()
            continue
        if line.startswith("#"):
            header = line[1:].split()
            lower = [v.lower() for v in header]
            if "sumw" in lower and "numentries" in lower:
                columns = (lower.index("sumw"), lower.index("numentries"), len(header))
            continue
        if columns is None or not line or line.startswith(("Total", "Underflow", "Overflow", "Edges(", "---")):
            continue
        parts = line.split()
        idx_w, idx_n, length = columns
        if len(parts) < length:
            continue
        try:
            weight = float(parts[idx_w])
            count = float(parts[idx_n])
        except ValueError:
            continue
        if not math.isfinite(count) or count < 0:
            raise ValueError(f"Bad numEntries in {current_path}: {count}")
        if count == 0:
            continue
        if not math.isfinite(weight):
            raise ValueError(f"Nonfinite sumW in populated bin: {current_path}")
        filled_bins += 1
        entries += count
        sumw += weight
    if current_type is not None:
        raise ValueError("Truncated YODA block (missing END)")
    if not records:
        raise ValueError("No AQP_WKTSPLITTINGS histogram objects with entry statistics found")
    if not any(rec[1] for rec in records):
        raise ValueError("No populated AQP_WKTSPLITTINGS histogram bins")
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("yoda", type=Path)
    args = parser.parse_args()
    if not args.yoda.is_file():
        parser.error(f"YODA file not found: {args.yoda}")
    op = gzip.open if args.yoda.name.endswith(".gz") else open
    try:
        with op(args.yoda, "rt", encoding="utf-8") as data:
            rows = inspect(data)
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))
    for path, bins, entries, sumw in rows:
        print(f"HIST {path} populated_bins={bins} entries={entries:g} sumW={sumw:.9g}")
    populated = sum(bins > 0 for _, bins, _, _ in rows)
    print(f"AQP_WKTS_YODA_POPULATED_PASS={populated}")
    print("NOTE: Not a normalization, error-propagation or physics-equivalence test.")


if __name__ == "__main__":
    main()
