#!/usr/bin/env python3
"""Validate an LHE v3 .events file and summarize MC@NLO weight signs.

For HT2-biased production, this measures the sign fractions of the
recorded nominal LHE XWGTUP values. It does not undo generation bias
or calculate a physical cross section.
"""
import argparse
import json
import math
from pathlib import Path
import re

EVENT_OPEN = re.compile(r"^\s*<event(?=\s|>)")
EVENT_CLOSE = re.compile(r"^\s*</event\s*>")

def inspect(path, expected):
    n_open = n_close = n_positive = n_negative = n_zero = 0
    in_event = False
    awaiting_header = False
    weights = []
    seen_lhe_end = False
    with path.open("r", encoding="utf-8", errors="replace") as source:
        for lineno, line in enumerate(source, 1):
            stripped = line.strip()
            if EVENT_OPEN.match(line):
                if in_event:
                    raise ValueError(f"nested event near line {lineno}")
                n_open += 1
                in_event = True
                awaiting_header = True
            elif EVENT_CLOSE.match(line):
                if not in_event or awaiting_header:
                    raise ValueError(f"invalid event end at line {lineno}")
                n_close += 1
                in_event = False
            elif stripped.startswith("</LesHouchesEvents>"):
                if in_event:
                    raise ValueError("LHE closed inside an event")
                seen_lhe_end = True
            elif in_event and awaiting_header and stripped:
                if stripped.startswith("#"):
                    continue
                if stripped.startswith("<"):
                    raise ValueError(f"non-header XML before event header at line {lineno}")
                fields = stripped.split()
                if len(fields) < 3:
                    raise ValueError(f"short event header at line {lineno}")
                try:
                    w = float(fields[2].replace("D", "E").replace("d", "e"))
                except ValueError as exc:
                    raise ValueError(f"malformed XWGTUP at line {lineno}") from exc
                if not math.isfinite(w):
                    raise ValueError(f"non-finite XWGTUP at line {lineno}")
                weights.append(w)
                if w > 0:
                    n_positive += 1
                elif w < 0:
                    n_negative += 1
                else:
                    n_zero += 1
                awaiting_header = False
    if in_event or n_open != n_close:
        raise ValueError(f"unclosed LHE event tags: {n_open}/{n_close}")
    if not seen_lhe_end:
        raise ValueError("missing </LesHouchesEvents>")
    if n_open != expected or len(weights) != expected:
        raise ValueError(f"expected {expected} events, got {n_open} ({len(weights)} weights)")
    abs_pos = math.fsum(w for w in weights if w > 0)
    abs_neg = math.fsum(-w for w in weights if w < 0)
    abs_total = abs_pos + abs_neg
    signed_sum = math.fsum(weights)
    nonzero_n = n_positive + n_negative
    raw_nwf_all = n_negative / n_open if n_open else None
    raw_nwf_nonzero = n_negative / nonzero_n if nonzero_n else None
    weighted_nwf = abs_neg / abs_total if abs_total > 0 else None
    dilution = None
    if weighted_nwf is not None and abs(1 - 2 * weighted_nwf) > 1e-14:
        dilution = 1 / (1 - 2 * weighted_nwf) ** 2
    return {
        "status": "PASS",
        "input": str(path),
        "num_events": n_open,
        "open_event_tags": n_open,
        "close_event_tags": n_close,
        "positive_weight_events": n_positive,
        "negative_weight_events": n_negative,
        "zero_weight_events": n_zero,
        "raw_negative_fraction_all_events": raw_nwf_all,
        "raw_negative_fraction_nonzero_events": raw_nwf_nonzero,
        "absolute_weighted_negative_fraction": weighted_nwf,
        "abs_positive_weight_sum": abs_pos,
        "abs_negative_weight_sum": abs_neg,
        "signed_weight_sum": signed_sum,
        "absolute_weight_sum": abs_total,
        "signed_weight_dilution": dilution,
        "note": (
            "Nominal LHE XWGTUP weight-sign diagnostics only. HT2 generation "
            "bias, FxFx matching losses, and cross-section normalization "
            "require separate validation."
        ),
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("events", type=Path)
    parser.add_argument("--expected-events", type=int, required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    args = parser.parse_args()
    if args.expected_events < 1:
        parser.error("expected-events must be positive")
    results = inspect(args.events, args.expected_events)
    if args.json_output.exists():
        parser.error("JSON output already exists")
    args.json_output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print("AQP_DELTA441_LHE_AUDIT_PASS=" + str(results["num_events"]))
    print("AQP_DELTA441_RAW_NWF=" + str(results["raw_negative_fraction_all_events"]))
    print("AQP_DELTA441_ABS_WEIGHTED_NWF=" + str(results["absolute_weighted_negative_fraction"]))

if __name__ == "__main__":
    main()
