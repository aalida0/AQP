#!/usr/bin/env python3
"""Identity-aware HTCondor status gate for an ISOLATED bundled MG5 candidate.

Scheduler terminal status does NOT establish GF output integrity. This is not
a complete production recovery controller: it requires a separate validated
output-manifest contract and AF-specific live testing.
"""
import json
import os
from pathlib import Path
import re
import subprocess


class CondorEvidenceError(RuntimeError):
    pass


def _ledger_root():
    raw = os.environ.get('AQP_CONDOR_INTENT_ROOT')
    if not raw or not os.path.isabs(raw):
        raise CondorEvidenceError('AQP_CONDOR_INTENT_ROOT not configured')
    root = Path(raw)
    if not root.is_dir() or root.is_symlink():
        raise CondorEvidenceError('Invalid Condor ledger root')
    return root


def _request_for_job(root, job):
    found = set()
    for path in root.glob('ack_AQP*.json'):
        try:
            record = json.loads(path.read_text(encoding='utf-8'))
            request_id = str(record['request_id'])
            cluster = str(record['cluster_id'])
        except (ValueError, KeyError, OSError, TypeError) as exc:
            raise CondorEvidenceError('Corrupt acknowledgement record') from exc
        if cluster == job:
            if not re.fullmatch(r'AQP[0-9a-f]{40}', request_id):
                raise CondorEvidenceError('Invalid request identifier')
            found.add(request_id)
    if len(found) != 1:
        raise CondorEvidenceError('No unique durable acknowledgement for job ' + job)
    request_id = next(iter(found))
    matching_intent = 0
    for path in root.glob('*.json'):
        if len(path.stem) != 64:
            continue
        try:
            payload = json.loads(path.read_text(encoding='utf-8'))
        except (ValueError, OSError, TypeError) as exc:
            raise CondorEvidenceError('Unreadable submission intent') from exc
        matching_intent += payload.get('request_id') == request_id
    if matching_intent != 1:
        raise CondorEvidenceError('Missing or duplicate intent for ACK')
    return request_id


def _run(command, runner):
    try:
        result = runner(command, capture_output=True, text=True,
                        timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CondorEvidenceError('Scheduler transport/timeout error') from exc
    if result.returncode != 0:
        raise CondorEvidenceError(
            'Scheduler query failed with code ' + str(result.returncode))
    return result.stdout.splitlines()


def check(job_id, runner=subprocess.run):
    """Return ACTIVE/TERMINATED only with matching durable ClassAd evidence.

    Never authorize a new submission, delete an intent, or certify GF output.
    The caller is responsible for retaining and checking required artifacts.
    """
    job = str(job_id)
    if not re.fullmatch(r'[1-9][0-9]*', job):
        raise CondorEvidenceError('Unsupported cluster ID')
    root = _ledger_root()
    token = _request_for_job(root, job)
    active = _run(['condor_q', job, '-af', 'ClusterId', 'ProcId',
                   'JobStatus', 'AQPRequestId'], runner)
    if active:
        if len(active) != 1:
            raise CondorEvidenceError('Ambiguous active queue response')
        parts = active[0].split()
        if (len(parts) != 4 or parts[0] != job or parts[1] != '0'
                or parts[3] != token):
            raise CondorEvidenceError('Mismatched active job identity')
        if parts[2] not in ('1', '2', '6', '7'):
            raise CondorEvidenceError('Unsupported active job state ' + parts[2])
        return 'ACTIVE'
    history = _run(['condor_history', job, '-af', 'ClusterId', 'ProcId',
                    'JobStatus', 'ExitCode', 'AQPRequestId'], runner)
    if len(history) != 1:
        raise CondorEvidenceError('No unique terminal history record')
    parts = history[0].split()
    if (len(parts) != 5 or parts[0] != job or parts[1] != '0'
            or parts[2] != '4' or parts[3] != '0' or parts[4] != token):
        raise CondorEvidenceError('Terminal history not proven successful and identical')
    return 'TERMINATED'
