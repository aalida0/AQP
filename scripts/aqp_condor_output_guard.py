#!/usr/bin/env python3
"""Fail-closed GF output gate for an ISOLATED MadGraph Condor candidate.

After independently verified HTCondor terminal success, require a complete
worker-published manifest and rehash every required GF output. This is not
production-ready until the actual worker publishes trusted request-bound
manifests, source/card provenance is frozen, and AF behavior is validated.
"""
import os
from pathlib import Path
import re

from . import aqp_condor_completion_guard as scheduler
from . import aqp_condor_output_manifest as manifest
from . import aqp_condor_submission_guard as submission


class CondorOutputError(RuntimeError):
    pass


def require_verified(job_id, retry=None):
    """Check immutable ACK output provenance, with optional MG retry cross-check.

    The durable ACK is independent of cluster_nb_retry. When MG retry_args
    exists it must AGREE with the ACK; never replace trusted records with
    a later mutable retry dictionary.
    """
    root = scheduler._ledger_root()
    try:
        context = submission.completion_context(root, job_id)
    except (submission.SubmissionSafetyError, scheduler.CondorEvidenceError) as exc:
        raise CondorOutputError("Missing/untrusted durable completion context") from exc
    cwd, outputs = context["cwd"], context["required_output"]
    if retry is not None:
        if (not isinstance(retry, dict)
                or not isinstance(retry.get("required_output"), (list, tuple))
                or not isinstance(retry.get("cwd"), str)
                or os.path.realpath(retry["cwd"]) != cwd
                or list(retry["required_output"]) != outputs):
            raise CondorOutputError("MG retry_args disagree with durable ACK")
    fingerprint = os.environ.get("AQP_CONDOR_INPUT_SHA256", "")
    if not re.fullmatch(r"[a-f0-9]{64}", fingerprint):
        raise CondorOutputError("Trusted input fingerprint is not configured")
    # Do not trust local files until the job and ClassAd identity are verified.
    state = scheduler.check(job_id)
    if state != "TERMINATED":
        raise CondorOutputError("Job has not been independently verified terminal")
    request_id = scheduler._request_for_job(root, str(job_id))
    intents = []
    for path in root.glob("*.json"):
        if not re.fullmatch(r"[a-f0-9]{64}\.json", path.name):
            continue
        try:
            import json
            item = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError) as exc:
            raise CondorOutputError("Corrupt submission intent") from exc
        if item.get("request_id") == request_id:
            intents.append(item)
    if len(intents) != 1:
        raise CondorOutputError("No unique matching durable GF intent")
    intent = intents[0]
    if os.path.realpath(str(cwd)) != intent.get("process"):
        raise CondorOutputError("GF working directory differs from submission intent")
    try:
        manifest.verify(
            root, cwd, request_id=request_id, cluster_id=str(job_id),
            input_sha256=fingerprint, process=intent["process"],
            stage=intent["stage"], gf=intent["gf"],
            required_output=outputs,
        )
    except (KeyError, manifest.ManifestError) as exc:
        raise CondorOutputError("Required GF output manifest invalid: " + str(exc)) from exc
    return True
