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


def reserve(prog, argument, cwd):
    """Reserve a durable GF/stage identity BEFORE creating condor_submit."""
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
    if not cwd or not os.path.isabs(str(cwd)):
        raise SubmissionSafetyError('GF working directory must be an absolute path')
    channel = os.path.realpath(str(cwd))
    if not os.path.isdir(channel):
        raise SubmissionSafetyError('GF channel working directory does not exist')
    request_id = 'AQP' + secrets.token_hex(20)
    try:
        ledger.claim(_root(), channel, 'MINT' + step, worker_group, request_id)
    except ledger.UnresolvedIntent as exc:
        raise SubmissionSafetyError('Existing GF submission intent; manual reconciliation required') from exc
    return request_id


def acknowledge(request_id, cluster_id):
    """Record a successful submit ACK; never clear prior unresolved intent."""
    if not re.fullmatch(r'AQP[0-9a-f]{40}', str(request_id)):
        raise SubmissionSafetyError('Bad request ID')
    if not str(cluster_id).isdigit() or int(cluster_id) <= 0:
        raise SubmissionSafetyError('Bad cluster ID')
    root = _root()
    output = root / ('ack_' + request_id + '.json')
    payload = (json.dumps({'request_id': request_id, 'cluster_id': str(cluster_id)},
                          sort_keys=True) + '\n').encode()
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
