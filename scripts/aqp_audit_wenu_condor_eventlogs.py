#!/usr/bin/env python3
"""Read-only history audit of Wenu MG5-internal HTCondor event logs.

Distinct submit event (000) IDs within one GF/stage log indicate separate
submitted jobs; repeated execute events (001) of one ID can reflect eviction
or restart. Missing logs never justify resubmission.

Does not contact HTCondor, import MadGraph, or modify files.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

CONFIGS = {"standard111": "standard111", "delta111": "delta111",
           "delta221": "delta221", "delta441_backup": "delta441"}
EVENT_RE = re.compile(r'^\s*(\d{3})\s+\((\d+)\.(\d+)\.(\d+)\)\s+')
RETURN_RE = re.compile(r'Normal termination\s*\(return value\s+(-?\d+)\)', re.I)
MINT_RE = re.compile(r'Fortran runtime error: Bad real number', re.I)
FILE_RE = re.compile(r'^(?P<subproc>.+)__GF(?P<gf>[^/]+)__step(?P<stage>[01])\.log$')
MAX_LOG_BYTES = 16_000_000


def read_eventlog(path):
    """Parse text event logs without inferring job state from absent records."""
    if path.stat().st_size > MAX_LOG_BYTES:
        raise ValueError("file exceeds read limit")
    events = []
    last_job = None
    with path.open('r', encoding='utf-8', errors='replace') as stream:
        for line in stream:
            m = EVENT_RE.match(line)
            if m:
                event, cluster, proc, _subproc = m.groups()
                last_job = "%s.%s" % (int(cluster), int(proc))
                events.append({"event": event, "id": last_job, "return": None})
                continue
            r = RETURN_RE.search(line)
            if (r and events and events[-1]["event"] == "005"
                    and events[-1]["id"] == last_job):
                events[-1]["return"] = int(r.group(1))
    ids = sorted({ev["id"] for ev in events if ev["event"] == "000"})
    executions = Counter(ev["id"] for ev in events if ev["event"] == "001")
    all_ids = sorted({ev["id"] for ev in events})
    return {
        "submit_ids": ids, "all_ids": all_ids,
        "repeated_execution_ids": sorted(job for job, n in executions.items() if n > 1),
        "unsubmitted_event_ids": sorted(set(all_ids) - set(ids)),
        "counts": dict(Counter(ev["event"] for ev in events)),
        "exit_codes": [ev["return"] for ev in events
                       if ev["event"] == "005" and ev["return"] is not None],
        "unparsed_exit_events": sum(ev["event"] == "005" and ev["return"] is None
                                    for ev in events),
    }


def find_failed_mint1_gfs(process):
    """Find GF directories with historical MINT1 bad-real error markers."""
    affected = set()
    root = process / 'SubProcesses'
    if not root.is_dir():
        return affected
    for path in root.glob('P*/GF*/log_MINT1.txt'):
        try:
            if path.stat().st_size > MAX_LOG_BYTES:
                continue
            if MINT_RE.search(path.read_text(encoding='utf-8', errors='replace')):
                affected.add((path.parent.parent.name, path.parent.name))
        except OSError:
            continue
    return affected


def assess(base, max_examples=12):
    summary = {}
    for config, timing_dirname in CONFIGS.items():
        process = base / config / 'PROCNLO_loop_sm-no_b_mass_0'
        timing = base / timing_dirname / 'aqp_condor_timing'
        failures = find_failed_mint1_gfs(process)
        record = {
            "timing_dir": str(timing), "timing_dir_exists": timing.is_dir(),
            "mint1_bad_real_gfs": len(failures), "matching_log_files": 0,
            "distinct_submit_job_ids": 0, "duplicate_submission_log_files": 0,
            "repeat_execute_log_files": 0, "evicted_log_files": 0,
            "nonzero_exit_log_files": 0, "missing_submit_log_files": 0,
            "unresolved_bad_real_gfs": [], "bad_real_with_distinct_submits": [],
            "duplicate_examples": [], "errors": [],
        }
        seen_for_errors = set()
        if timing.is_dir():
            for path in sorted(timing.glob('*.log')):
                m = FILE_RE.fullmatch(path.name)
                if not m:
                    continue
                subproc, gf, stage = m.group('subproc', 'gf', 'stage')
                record['matching_log_files'] += 1
                try:
                    data = read_eventlog(path)
                except (OSError, ValueError) as error:
                    record['errors'].append("%s: %s" % (path.name, error))
                    continue
                submits = data['submit_ids']
                record['distinct_submit_job_ids'] += len(submits)
                if not submits:
                    record['missing_submit_log_files'] += 1
                if len(submits) > 1:
                    record['duplicate_submission_log_files'] += 1
                    if len(record['duplicate_examples']) < max_examples:
                        record['duplicate_examples'].append({
                            "file": path.name, "submitted_job_ids": submits,
                        })
                if data['repeated_execution_ids']:
                    record['repeat_execute_log_files'] += 1
                if data['counts'].get('004', 0):
                    record['evicted_log_files'] += 1
                if any(code != 0 for code in data['exit_codes']):
                    record['nonzero_exit_log_files'] += 1
                key = (subproc, 'GF' + gf)
                if stage == '1' and key in failures:
                    seen_for_errors.add(key)
                    if len(submits) > 1:
                        if len(record['bad_real_with_distinct_submits']) < max_examples:
                            record['bad_real_with_distinct_submits'].append({
                                'subprocess': subproc, 'gf': 'GF' + gf,
                                'submitted_job_ids': submits,
                            })
        record['unresolved_bad_real_gfs'] = [
            '%s/%s' % (p, g)
            for p, g in sorted(failures - seen_for_errors)[:max_examples]]
        record['bad_real_with_any_step1_log'] = len(seen_for_errors)
        record['remaining_unmatched_bad_real_count'] = len(failures - seen_for_errors)
        summary[config] = record
    return summary


def print_report(result):
    print('AQP WENU INTERNAL CONDOR EVENT-LOG AUDIT (READ ONLY)')
    for name, info in result.items():
        print('=== %s ===' % name)
        print('timing_dir:', info['timing_dir'])
        if not info['timing_dir_exists']:
            print('NO_LOG_DIRECTORY (not evidence of zero submissions)')
        for key in ('matching_log_files', 'distinct_submit_job_ids',
                    'duplicate_submission_log_files', 'repeat_execute_log_files',
                    'evicted_log_files', 'nonzero_exit_log_files',
                    'missing_submit_log_files', 'mint1_bad_real_gfs',
                    'bad_real_with_any_step1_log', 'remaining_unmatched_bad_real_count'):
            print('%s: %s' % (key, info[key]))
        for key in ('duplicate_examples', 'bad_real_with_distinct_submits',
                    'unresolved_bad_real_gfs', 'errors'):
            if info[key]:
                print(key + ':', json.dumps(info[key]))
    print('NOTE: repeated executions of one job may follow eviction; >1')
    print('distinct submit ID in one GF/stage log indicates separate submissions.')
    print('Missing logs or successful exits do NOT prove grid integrity or')
    print('authorize resubmission. No scheduler queries or changes were made.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--max-examples', type=int, default=12)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    if args.max_examples < 0:
        parser.error('--max-examples must be >= 0')
    if not args.base.is_dir():
        parser.error('--base is not an existing directory')
    result = assess(args.base, args.max_examples)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print_report(result)


if __name__ == '__main__':
    main()
