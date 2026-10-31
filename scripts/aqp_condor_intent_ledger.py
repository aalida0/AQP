#!/usr/bin/env python3
"""Prototype write-once MG5 internal-Condor submission intent ledger.

UNINTEGRATED SAFETY COMPONENT. This module never submits/queries HTCondor,
patches MadGraph, or writes into production unless a caller explicitly selects
its state directory. Do not use it as a production controller.

An intent is permanently reserved before attempting condor_submit. The
ledger does not clear records automatically: successful job exit, empty
condor_q, absent history, and a locally existing GF artifact are individually
insufficient to authorize another submission.
"""

import hashlib
import json
import os
from pathlib import Path
import re


class UnresolvedIntent(RuntimeError):
    """Submission identity already exists or is not safely recoverable."""


def _valid(s):
    return isinstance(s, str) and 0 < len(s) <= 256 and bool(re.fullmatch(r"[A-Za-z0-9_.:@/-]+", s))


def identity(process, stage, gf):
    if not all(_valid(x) for x in (process, stage, gf)):
        raise ValueError("Invalid process/stage/GF identity")
    values = {"process": process, "stage": stage, "gf": gf}
    blob = json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest(), values


def claim(root, process, stage, gf, request_id):
    """Durably reserve one (process,stage,GF) once; never overwrite/retry.

    The caller must invoke claim BEFORE condor_submit and put request_id in
    the submit ClassAd. If the controller dies, even mid-write, the key stays
    reserved. For a recoverable production version, the storage backend and
    fsync guarantees must be qualified on the chosen AF shared filesystem.
    """
    if not _valid(request_id):
        raise ValueError("Invalid request ID")
    key, values = identity(process, stage, gf)
    directory = Path(root)
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError("Ledger root must be an existing real directory")
    path = directory / (key + ".json")
    record = dict(values, request_id=request_id, state="INTENT_UNRESOLVED", version=1)
    payload = (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode()
    try:
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise UnresolvedIntent("GF/stage already has an intent: " + key) from exc
    # Do NOT remove a partially written intent after any failure: a scheduler
    # call might already have happened in the outer controller.
    with os.fdopen(fd, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    parent_fd = os.open(str(directory), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)
    return record


def read(root, process, stage, gf):
    key, values = identity(process, stage, gf)
    path = Path(root) / (key + ".json")
    raw = path.read_bytes()
    record = json.loads(raw)
    if (record.get("version") != 1 or record.get("state") != "INTENT_UNRESOLVED"
            or any(record.get(k) != v for k, v in values.items())
            or not _valid(record.get("request_id"))):
        raise UnresolvedIntent("Invalid/corrupt intent: " + key)
    return record


def reconcile(record, *, queue, history, artifact):
    """Pure decision: never authorize resubmit (caller decides external actions).

    queue/history must be complete, authoritative *results for request_id*,
    not a bulk-queue absence inference. Each is a dict with
    'reliable' and 'records' fields; records contain request_id, job_id,
    state, and for history exit_code. artifact is a dict with verified,
    matching_request_id and complete_manifest booleans from an INDEPENDENT
    checker, not from file existence alone.
    """
    request_id = record.get("request_id")
    if not _valid(request_id):
        return "BLOCK_INVALID_INTENT"
    if not isinstance(queue, dict) or not isinstance(history, dict):
        return "BLOCK_SCHEDULER_UNAVAILABLE"
    if not queue.get("reliable") or not history.get("reliable"):
        return "BLOCK_SCHEDULER_UNAVAILABLE"
    records = list(queue.get("records", [])) + list(history.get("records", []))
    if any(r.get("request_id") != request_id for r in records):
        return "BLOCK_IDENTITY_MISMATCH"
    job_ids = {str(r.get("job_id")) for r in records}
    if len(job_ids) > 1:
        return "BLOCK_DUPLICATE_JOBS"
    if queue.get("records"):
        return "BLOCK_JOB_ACTIVE"
    terminal = history.get("records", [])
    if len(terminal) != 1 or terminal[0].get("state") != "TERMINATED":
        return "BLOCK_UNKNOWN_JOB_STATE"
    if terminal[0].get("exit_code") != 0:
        return "BLOCK_FAILED_JOB"
    if not isinstance(artifact, dict) or not (
        artifact.get("verified") is True
        and artifact.get("matching_request_id") is True
        and artifact.get("complete_manifest") is True
    ):
        return "BLOCK_UNVERIFIED_OUTPUT"
    return "TERMINAL_VERIFIED_NO_AUTOMATIC_RESUBMISSION"
