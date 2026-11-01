#!/usr/bin/env python3
"""Read-only audit of PMG PDF/scale weight inventory in an LHE file.

Examples:
  python3 scripts/audit_zee1jet_weight_inventory.py \
    ~/gridpack-validation/zee1jet.cC7MYdWf/events.lhe --max-events 10

The archive, JO, generated file and events are never modified.
"""
import argparse
import gzip
import json
import math
from pathlib import Path
import re


HEADER_WEIGHT = re.compile(
    r'<weight\s+id=["\x27]([^"\x27]+)["\x27][^>]*>\s*([^<]+)\s*</weight>'
)
EVENT_WEIGHT = re.compile(
    r'<wgt\s+id=["\x27]([^"\x27]+)["\x27][^>]*>\s*([^<]+)\s*</wgt>'
)
START_EVENT = re.compile(r'^\s*<event(?:\s[^>]*)?>')
CENTRAL = 'MUR1.0_MUF1.0_PDF325100'
ANTI = ('MUR0.5_MUF2.0_PDF325100',
        'MUR2.0_MUF0.5_PDF325100')
ALTERNATIVES = {
    304400, 13000, 25300, 14000, 14100, 14200, 61200,
    42560, 303200, 27400, 331500,
}
SCALE_RE = re.compile(r'^MUR([0-9.]+)_MUF([0-9.]+)_PDF325100$')
PDF_RE = re.compile(r'^MUR1\.0_MUF1\.0_PDF(\d+)$')


def inspect(path, max_events=10):
    opener = gzip.open if path.suffix == '.gz' else open
    definitions = {}
    duplicates = []
    event_counts = []
    missing_ids = []
    bad_weight_examples = []
    compact_events = 0
    event_ids = set()
    all_defined = set()
    in_event = False
    current = {}
    events_inspected = 0
    with opener(path, 'rt', errors='replace') as stream:
        for line in stream:
            if not in_event:
                if START_EVENT.match(line):
                    in_event = True
                    current = {}
                    continue
                match = HEADER_WEIGHT.search(line)
                if match:
                    wid, name = match.groups()
                    if wid in definitions:
                        duplicates.append(wid)
                    definitions[wid] = name.strip()
                    all_defined.add(wid)
                continue
            if '<weights>' in line or '<weights ' in line:
                compact_events += 1
            for match in EVENT_WEIGHT.finditer(line):
                wid, value = match.groups()
                event_ids.add(wid)
                try:
                    number = float(value.strip().replace('d', 'e').replace('D', 'E'))
                    if not math.isfinite(number):
                        raise ValueError('nonfinite')
                except ValueError:
                    bad_weight_examples.append((events_inspected + 1, wid, value[:60]))
                current[wid] = current.get(wid, 0) + 1
            if '</event>' in line:
                events_inspected += 1
                event_counts.append(len(current))
                if len(missing_ids) < 3:
                    absent = sorted(all_defined - set(current))
                    extra = sorted(set(current) - all_defined)
                    repeated = sorted(k for k, v in current.items() if v != 1)
                    if absent or extra or repeated:
                        missing_ids.append({
                            'event': events_inspected,
                            'missing_count': len(absent),
                            'missing_examples': absent[:12],
                            'extra_examples': extra[:12],
                            'repeated_examples': repeated[:12],
                        })
                in_event = False
                if events_inspected >= max_events:
                    break
    labels = list(definitions.values())
    pdfs = [
        int(match.group(1))
        for label in labels
        if (match := PDF_RE.match(label)) is not None
    ]
    scales = [label for label in labels if SCALE_RE.match(label)]
    categories = {
        'noncentral_scale': len([w for w in scales if w != CENTRAL]),
        'nnpdf31_luxqed': sum(325100 <= p <= 325200 for p in pdfs),
        'pdf4lhc21_pdfas': sum(93300 <= p <= 93342 for p in pdfs),
        'alternative_pdfs': sum(p in ALTERNATIVES for p in pdfs),
    }
    values_valid = (
        bool(events_inspected) and not missing_ids
        and not bad_weight_examples and not compact_events
        and all(c == len(definitions) for c in event_counts)
    )
    return {
        'source': str(path),
        'header_weight_count': len(definitions),
        'weight_id_count_unique': len(all_defined),
        'header_duplicate_ids': duplicates[:20],
        'weight_ids_contiguous_1_to_163': (
            all_defined == {str(i) for i in range(1, 164)}
        ),
        'category_counts': categories,
        'category_counts_sum': sum(categories.values()),
        'central_weight_present': CENTRAL in labels,
        'anti_correlated_scale_weights_present':
            {name: name in labels for name in ANTI},
        'events_checked': events_inspected,
        'event_variation_weight_counts': event_counts,
        'event_variation_weight_ids_seen': len(event_ids),
        'compact_weight_block_events': compact_events,
        'event_weight_issues': missing_ids,
        'nonfinite_or_non_numeric_examples': bad_weight_examples[:10],
        'event_level_163_weight_inventory_valid': (
            values_valid and len(definitions) == 163
            and all_defined == {str(i) for i in range(1, 164)}
        ),
        'status': 'AUDIT_ONLY: weight inventory, not full PDF/scale physics validation',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('lhe', type=Path)
    parser.add_argument('--max-events', type=int, default=10)
    args = parser.parse_args()
    if args.max_events < 1:
        parser.error('--max-events must be positive')
    path = args.lhe.expanduser().resolve(strict=True)
    if not path.is_file():
        parser.error(f'Not a file: {path}')
    print(json.dumps(inspect(path, args.max_events),
                     indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
