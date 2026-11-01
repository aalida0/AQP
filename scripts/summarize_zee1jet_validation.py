#!/usr/bin/env python3
"""Summarize a Zee 0,1j gridpack validation directory without modifying it.

Keep stages separate: LHE negative weights are *before* FxFx veto/shower;
post-FxFx negative-weight fractions require accepted-event weights.
Missing counters are explicitly reported as unknown, never guessed.
"""
import argparse
import gzip
import json
from pathlib import Path
import re


CENTRAL = "MUR1.0_MUF1.0_PDF325100"


def read_parameters(path):
    result = {}
    if path.exists():
        for line in path.read_text(errors="replace").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                result[key] = value
    return result


def find_lhe(run):
    # Only use the combined LHE output, NOT raw GF subprocess event files.
    candidates = list(run.glob("*.lhe")) + list(run.glob("*.lhe.gz"))
    candidates += list(run.glob("*.events")) + list(run.glob("*.events.gz"))
    candidates += list((run / "madevent" / "Events").glob("*/*.lhe*"))
    return next((p for p in sorted(set(candidates),
                                  key=lambda x: (-x.stat().st_size, str(x)))
                 if p.is_file() and p.stat().st_size), None)


def inspect_lhe(path):
    opener = gzip.open if path.suffix == ".gz" else open
    positive, negative, npos, nneg, nev = 0., 0., 0, 0, 0
    central_seen = False
    number_ids = set()
    in_header = True
    with opener(path, "rt", errors="replace") as infile:
        for line in infile:
            if in_header:
                if CENTRAL in line:
                    central_seen = True
                if "<weight " in line:
                    weight_id = re.search(r"<weight\s+id=['\"]([^'\"]+)", line)
                    if weight_id:
                        number_ids.add(weight_id.group(1))
                if "</header>" in line:
                    in_header = False
            if not re.match(r"^\s*<event(?:\s[^>]*)?>", line):
                continue
            event_line = next(infile, "")
            items = event_line.split()
            if len(items) < 3:
                raise ValueError(f"Malformed LHE event header in {path}")
            try:
                w = float(items[2].replace("D", "E").replace("d", "e"))
            except ValueError as err:
                raise ValueError(f"Invalid LHE nominal weight in {path}: {items[2]}") from err
            nev += 1
            if w < 0:
                negative += abs(w)
                nneg += 1
            elif w > 0:
                positive += w
                npos += 1
    total_abs = positive + negative
    f = negative / total_abs if total_abs else None
    u = nneg / nev if nev else None
    return {
        "lhe_events": nev,
        "sum_positive_nominal_abs": positive,
        "sum_negative_nominal_abs": negative,
        "unweighted_lhe_negative_fraction": u,
        "weighted_lhe_negative_fraction": f,
        "weighted_lhe_dilution_1_over_1_minus_2f_squared":
            (1.0 / (1 - 2*f)**2 if f is not None and abs(1 - 2*f) > 1e-12 else None),
        "lhe_header_contains_central_pmg_weight_name": central_seen,
        "lhe_header_weight_ids_count": len(number_ids),
        "stage": "LHE, before FxFx shower veto",
    }


def parse_shower_counters(log):
    # Only accept explicitly labeled counters. Do not infer 'tried'
    # from generated LHE or 'accepted' from EVNT event count.
    tried, accepted = None, None
    evidence = []
    for line in log.splitlines():
        line_lower = line.lower()
        if re.search(r"\b(?:fxfx|pythia8|merging|veto|sumofposweights|sumofnegweights)\b", line_lower):
            if re.search(r"\b(?:accepted|selected|tried|efficien|veto|merg|sumofposweights|sumofnegweights)\b", line_lower):
                evidence.append(line[:300].strip())
        for label in ("tried", "accepted"):
            match = re.search(
                rf"\b(?:number\s+of\s+)?(?:events\s+)?{label}\s*[:=]\s*([\d,]+)\b",
                line, re.IGNORECASE
            )
            if match and re.search("pythia|merg|fxfx", line, re.IGNORECASE):
                if label == "tried":
                    tried = int(match.group(1).replace(",", ""))
                else:
                    accepted = int(match.group(1).replace(",", ""))
    return {
        "pythia_events_tried_explicit": tried,
        "pythia_events_accepted_explicit": accepted,
        "fxfx_matching_efficiency_from_explicit_counters":
            accepted / tried if tried and accepted is not None else None,
    }, evidence[-40:]


def summarize(run):
    parameters = read_parameters(run / "validation_parameters.txt")
    main_log_path = run / "generation_shower.log"
    log = main_log_path.read_text(errors="replace") if main_log_path.is_file() else ""
    evnt = run / "zee1jet.EVNT.pool.root"
    lhe = find_lhe(run)
    pythia, evidence = parse_shower_counters(log)
    transform_ok = parameters.get("transform_exit") == "0"
    verified_path = run / "evnt_count_verified.txt"
    verified_count = None
    if verified_path.is_file():
        verified_text = verified_path.read_text().strip()
        if verified_text.isdigit():
            verified_count = int(verified_text)
    expected = parameters.get("maxEvents")
    summary = {
        "run": str(run),
        "input_parameters": parameters,
        "transform_exit_zero": transform_ok,
        "evnt_exists_nonempty": evnt.is_file() and evnt.stat().st_size > 0,
        "evnt_events_requested": int(expected) if expected and expected.isdigit() else None,
        # This marker is written only after the caller's PyROOT
        # CollectionTree.GetEntries() check has succeeded.
        "evnt_count_confirmed_in_validation_wrapper": verified_count,
        "arrange_output_central_pmg_weight_check_passed":
            transform_ok and CENTRAL in log and
            "Did not find expected weight" not in log,
        "lhe_file": str(lhe) if lhe else None,
        "lhe_pre_fxfx": inspect_lhe(lhe) if lhe else None,
        "post_fxfx_negative_weight_fraction": None,
        "post_fxfx_negative_weight_fraction_status":
            "UNKNOWN: requires accepted EVNT nominal weight sums; LHE is pre-veto",
        "pythia8_counters": pythia,
        "pythia8_statistic_evidence_lines": evidence,
    }
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--json", type=Path,
                        help="Save JSON; omit to print only (read-only)")
    args = parser.parse_args()
    run = args.run.expanduser().resolve(strict=True)
    if not run.is_dir():
        parser.error(f"No directory at {run}")
    result = summarize(run)
    formatted = json.dumps(result, indent=2, sort_keys=True)
    print(formatted)
    if args.json:
        destination = args.json.expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(formatted + "\n")
        print("REPORT_WRITTEN", destination)


if __name__ == "__main__":
    main()
