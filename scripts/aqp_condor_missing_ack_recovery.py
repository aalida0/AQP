#!/usr/bin/env python3
"""Experimental, fail-closed recovery of MG5 Condor submissions with lost ACK.

Does not resubmit, remove or cancel any job. Default is READ-ONLY; commit=True
may write one durable acknowledgement only after finding exactly ONE matching
job by AQPRequestId in the active queue OR history. This is not integrated
with MG5 and is NOT a production or physics-output completion mechanism.

Important: no scheduler results (even successful, empty ones) prove that an
unacknowledged request was never accepted. Therefore unknown stays blocked.
"""
import json
from pathlib import Path
import re
import subprocess

from . import aqp_condor_intent_ledger as ledger


class RecoveryBlocked(RuntimeError):
    pass


def _root(root):
    folder = Path(root)
    if folder.is_symlink() or not folder.is_dir():
        raise RecoveryBlocked("Missing or symlinked intent root")
    return folder.resolve(strict=True)


def _intent(root, request_id):
    if not re.fullmatch(r"AQP[0-9a-f]{40}", str(request_id)):
        raise RecoveryBlocked("Invalid AQP request ID")
    matched = []
    for path in root.glob("*.json"):
        if not re.fullmatch(r"[0-9a-f]{64}\.json", path.name):
            continue
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
            key, _ = ledger.identity(item["process"], item["stage"], item["gf"])
            if key != path.stem:
                raise RecoveryBlocked("Intent filename/identity mismatch")
            if item.get("request_id") == request_id:
                matched.append(item)
        except (OSError, KeyError, ValueError, TypeError) as exc:
            raise RecoveryBlocked("Corrupt durable submission intent") from exc
    if len(matched) != 1:
        raise RecoveryBlocked("No unique unresolved submission intent")
    intent = matched[0]
    context = intent.get("pre_submit_context")
    if context is None:
        raise RecoveryBlocked("Submission predates durable context capture")
    try:
        validated = ledger._worker_context(
            context, intent["process"], intent["stage"], intent["gf"])
    except (ValueError, KeyError, TypeError) as exc:
        raise RecoveryBlocked("Invalid durable pre-submit worker context") from exc
    return intent, validated


def _query(command, runner):
    try:
        completed = runner(command, capture_output=True, text=True,
                           timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RecoveryBlocked("HTCondor query transport error") from exc
    if completed.returncode != 0:
        raise RecoveryBlocked("HTCondor query failed with status " +
                              str(completed.returncode))
    if not isinstance(completed.stdout, str):
        raise RecoveryBlocked("Nontext scheduler response")
    return [row.split() for row in completed.stdout.splitlines() if row.strip()]


def _match(rows, request_id, history):
    found = []
    for parts in rows:
        if len(parts) != (5 if history else 4):
            raise RecoveryBlocked("Malformed HTCondor ClassAd reply")
        cluster, proc, token, status = parts[:4]
        if (not re.fullmatch(r"[1-9][0-9]*", cluster)
                or proc != "0" or token != request_id
                or status not in ("1", "2", "3", "4", "5", "6", "7")):
            raise RecoveryBlocked("Foreign or unsupported HTCondor reply")
        if history:
            if status != "4" or not re.fullmatch(r"-?[0-9]+", parts[4]):
                raise RecoveryBlocked("History does not have a terminal exit code")
        found.append((cluster, proc))
    return found


def recover(root, request_id, *, runner=subprocess.run, commit=False):
    """Locate one scheduler submission by durable token; do not auto-resubmit.

    commit=True is an explicit operator action writing an ACK. The returned
    state ACK_RECOVERED is NOT evidence of valid GF results. An ambiguity or
    failed lookup must not allow a second submission.
    """
    directory = _root(root)
    _record, context = _intent(directory, request_id)
    constraint = 'AQPRequestId == "%s"' % request_id
    active = _match(
        _query(["condor_q", "-constraint", constraint, "-af",
                "ClusterId", "ProcId", "AQPRequestId", "JobStatus"], runner),
        request_id, False)
    history = _match(
        _query(["condor_history", "-constraint", constraint, "-af",
                "ClusterId", "ProcId", "AQPRequestId", "JobStatus", "ExitCode"], runner),
        request_id, True)
    if (len(active) > 1 or len(history) > 1
            or len(set(active + history)) != 1
            or (active and history)):
        raise RecoveryBlocked("Missing/duplicate/conflicting scheduler identity")
    job = (active + history)[0][0]
    from . import aqp_condor_submission_guard as submission
    existing = directory / ("ack_" + request_id + ".json")
    if existing.exists() or existing.is_symlink():
        raise RecoveryBlocked("Acknowledgment already exists; verify existing state")
    result = {
        "request_id": request_id,
        "cluster_id": job,
        "recovered_from": "queue" if active else "history",
        "acknowledged": False,
        "automatic_resubmission_allowed": False,
    }
    if commit:
        # An ACK can always fail after the scheduler accepted the original job.
        # No retry is attempted here; restart can replay the same token.
        submission.acknowledge(
            request_id, job, context["cwd"], context["required_output"])
        result["acknowledged"] = True
    return result
