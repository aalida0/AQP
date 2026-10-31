#!/usr/bin/env python3
"""Experimental durable submission fence for MG5 bundled internal Condor.

UNINTEGRATED candidate. Never use in physics production: status/history
reconciliation, output validation and crash recovery remain incomplete.
"""
import json
import os
from pathlib import Path
import re
import secrets

from . import aqp_condor_intent_ledger as ledger


class SubmissionSafetyError(RuntimeError):
    pass


def _root():
    raw = os.environ.get('AQP_CONDOR_INTENT_ROOT')
    if not raw or not os.path.isabs(raw):
        raise SubmissionSafetyError('AQP_CONDOR_INTENT_ROOT must be an absolute path to an existing isolated directory')
    path = Path(raw)
    if not path.is_dir() or path.is_symlink():
        raise SubmissionSafetyError('Submission ledger root must be a real existing directory')
    return path


def _outputs(required_output):
    """Normalize the exact MadGraph required_output relative paths."""
    if not isinstance(required_output, (list, tuple)) or not required_output:
        raise SubmissionSafetyError('Missing required_output for ajob1 worker')
    output = []
    for item in required_output:
        if not isinstance(item, str) or not item or item.startswith('/'):
            raise SubmissionSafetyError('Required output must be a relative path')
        parts = item.split('/')
        if any(part in ('', '.', '..') for part in parts):
            raise SubmissionSafetyError('Unsafe required_output path')
        output.append(item)
    if len(output) != len(set(output)):
        raise SubmissionSafetyError('Duplicate required output path')
    return output


def reserve(prog, argument, cwd, required_output):
    """Reserve a worker identity and validated output contract BEFORE submission."""
    if os.path.basename(str(prog)) != 'ajob1':
        raise SubmissionSafetyError('Unrecognized executable: only tested ajob1 GF submissions are supported')
    # MG5 3.5.11 ajob1 arguments are (channel, run_mode, runnumber,
    # integration_step). A single worker can process MULTIPLE G* directories.
    # In particular, argument[0] is not a GF directory/unique job identity.
    if not isinstance(argument, (list, tuple)) or len(argument) != 4:
        raise SubmissionSafetyError('Expected exactly four original ajob1 arguments')
    channel, run_mode, runnumber, step = map(str, argument)
    if (not all(re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', part)
                for part in (channel, run_mode, runnumber))
            or step not in ('0', '1')):
        raise SubmissionSafetyError('Unknown GF/stage argument format; refusing submission')
    # This ledger field names the WHOLE worker submission group, not a GF.
    # The ledger API retains its historical field name 'gf' until the
    # next versioned schema migration; do not infer single-GF semantics.
    worker_group = 'ajob1:' + ':'.join((channel, run_mode, runnumber))
    # Catch malformed/missing output contracts BEFORE reserving an intent
    # or invoking condor_submit. Exact strings originate in getIO_ajob().
    _outputs(required_output)
    if not cwd or not os.path.isabs(str(cwd)):
        raise SubmissionSafetyError('GF working directory must be an absolute path')
    channel = os.path.realpath(str(cwd))
    if not os.path.isdir(channel):
        raise SubmissionSafetyError('GF channel working directory does not exist')
    request_id = 'AQP' + secrets.token_hex(20)
    try:
        ledger.claim(
            _root(), channel, 'MINT' + step, worker_group, request_id,
            context={'cwd': channel, 'argument': [str(x) for x in argument],
                     'required_output': _outputs(required_output)})
    except ledger.UnresolvedIntent as exc:
        raise SubmissionSafetyError('Existing GF submission intent; manual reconciliation required') from exc
    return request_id


def acknowledge(request_id, cluster_id, cwd, required_output):
    """Persist independently usable MG completion context (even if nb_retry=0)."""
    """Record a successful submit ACK; never clear prior unresolved intent."""
    if not re.fullmatch(r'AQP[0-9a-f]{40}', str(request_id)):
        raise SubmissionSafetyError('Bad request ID')
    if not str(cluster_id).isdigit() or int(cluster_id) <= 0:
        raise SubmissionSafetyError('Bad cluster ID')
    if not isinstance(cwd, str) or not os.path.isabs(cwd):
        raise SubmissionSafetyError('Expected absolute worker directory')
    # Store exactly what MG passed to submit()/submit2(), before a possible
    # controller crash. This context is NOT a substitute for worker-side proof.
    output_paths = _outputs(required_output)
    root = _root()
    output = root / ('ack_' + request_id + '.json')
    payload = (json.dumps({
        'version': 2,
        'request_id': request_id,
        'cluster_id': str(cluster_id),
        'cwd': os.path.realpath(cwd),
        'required_output': output_paths,
    }, sort_keys=True) + '\n').encode()
    try:
        fd = os.open(str(output), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise SubmissionSafetyError('Duplicate acknowledgment record') from exc
    with os.fdopen(fd, 'wb') as fh:
        fh.write(payload)
        fh.flush()
        os.fsync(fh.fileno())
    fd = os.open(str(root), os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return str(output)

def completion_context(root, job_id):
    """Recover immutable output requirements from a durable ACK record.

    Must agree with the scheduler request-ID before trusting the context.
    This resolves absent MG retry_args, not unacknowledged submissions.
    """
    job = str(job_id)
    if not job.isdigit() or int(job) <= 0:
        raise SubmissionSafetyError('Invalid job id for output context')
    from . import aqp_condor_completion_guard as scheduler
    request_id = scheduler._request_for_job(root, job)
    record = root / ('ack_' + request_id + '.json')
    try:
        data = json.loads(record.read_text(encoding='utf-8'))
    except (OSError, ValueError, TypeError) as exc:
        raise SubmissionSafetyError('Corrupt durable job output context') from exc
    if (not isinstance(data, dict) or set(data) !=
            {'version', 'request_id', 'cluster_id', 'cwd', 'required_output'}
            or data['version'] != 2
            or data['request_id'] != request_id or data['cluster_id'] != job
            or not isinstance(data['cwd'], str)
            or not os.path.isabs(data['cwd'])):
        raise SubmissionSafetyError('Untrusted durable output context')
    outputs = _outputs(data['required_output'])
    return {'cwd': data['cwd'], 'required_output': outputs}
