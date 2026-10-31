#!/usr/bin/env python3
"""Experimental GF output manifest, with independent byte-level verification.

NON-PRODUCTION: no MadGraph worker invokes this publisher, and the current
CondorCluster completion path does not yet consume it. This module establishes
a narrowly testable contract only. Do not regard it as a grid-integrity check
for historical MG integrations or as permission to resubmit any GF.

A manifest is a write-once, atomically published assertion from a worker.
Verification independently rehashes every required file and compares the
trusted request/job/physics-input identity supplied by the controller.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import secrets

class ManifestError(RuntimeError):
    pass

def _hex64(value):
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{64}", value))

def _request(value):
    return isinstance(value, str) and bool(re.fullmatch(r"AQP[0-9a-f]{40}", value))

def _job(value):
    return str(value).isdigit() and int(value) > 0

def _root(directory):
    root = Path(directory)
    if root.is_symlink() or not root.is_dir():
        raise ManifestError("Manifest directory must exist and not be a symlink")
    return root.resolve(strict=True)

def _workdir(directory):
    workdir = Path(directory)
    if workdir.is_symlink() or not workdir.is_dir():
        raise ManifestError("Work directory must exist and not be a symlink")
    return workdir.resolve(strict=True)

def _file(workdir, relative):
    if not isinstance(relative, str) or not relative or relative.startswith("/"):
        raise ManifestError("Output paths must be nonempty relative paths")
    segments = Path(relative).parts
    if any(x in (".", "..") for x in segments) or Path(relative).is_absolute():
        raise ManifestError("Traversal in output path")
    source = workdir.joinpath(relative)
    if source.is_symlink() or not source.is_file():
        raise ManifestError("Missing/linked required output " + relative)
    resolved = source.resolve(strict=True)
    if workdir not in resolved.parents:
        raise ManifestError("Output escapes work directory")
    return resolved

def _hash(path):
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            total += len(chunk)
    if total <= 0:
        raise ManifestError("Required output is empty: " + str(path))
    return {"bytes": total, "sha256": digest.hexdigest()}

def _expect(expected_outputs):
    if not isinstance(expected_outputs, (list, tuple)) or not expected_outputs:
        raise ManifestError("Expected output list is empty")
    if not all(isinstance(item, str) for item in expected_outputs):
        raise ManifestError("Expected output names must be strings")
    if len(expected_outputs) != len(set(expected_outputs)):
        raise ManifestError("Duplicate output names")
    return sorted(expected_outputs)

def _identity(request_id, cluster_id, input_sha256, process, stage, gf):
    if not _request(request_id) or not _job(cluster_id) or not _hex64(input_sha256):
        raise ManifestError("Invalid request, cluster, or input fingerprint")
    if not all(isinstance(x, str) and x for x in (process, stage, gf)):
        raise ManifestError("Missing GF/stage/process identity")
    return {
        "version": 1,
        "request_id": request_id,
        "cluster_id": str(cluster_id),
        "input_sha256": input_sha256,
        "process": process,
        "stage": stage,
        "gf": gf,
    }

def publish(root, workdir, *, request_id, cluster_id, input_sha256,
            process, stage, gf, required_output):
    """Write once after successful worker completion; never replace an old claim."""
    output_dir, folder = _root(root), _workdir(workdir)
    identity = _identity(request_id, cluster_id, input_sha256, process, stage, gf)
    paths = _expect(required_output)
    files = {}
    for name in paths:
        files[name] = _hash(_file(folder, name))
    payload = dict(identity, files=files)
    destination = output_dir / ("complete_" + request_id + ".json")
    temporary = output_dir / (".pending_" + request_id + "_" + secrets.token_hex(8))
    data = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    try:
        fd = os.open(str(temporary), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(str(temporary), str(destination))
        fd = os.open(str(output_dir), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except FileExistsError as exc:
        raise ManifestError("Completion manifest already exists; refusing replacement") from exc
    finally:
        # If publication failed, no complete_ file was created. A stale
        # .pending_ file can remain only if cleanup itself fails.
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    return destination

def verify(root, workdir, *, request_id, cluster_id, input_sha256,
           process, stage, gf, required_output):
    """Fail closed on absent/changed artifact, identity, or source fingerprint."""
    output_dir, folder = _root(root), _workdir(workdir)
    identity = _identity(request_id, cluster_id, input_sha256, process, stage, gf)
    paths = _expect(required_output)
    path = output_dir / ("complete_" + request_id + ".json")
    if path.is_symlink() or not path.is_file():
        raise ManifestError("No trusted published completion manifest")
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, ValueError, OSError) as exc:
        raise ManifestError("Invalid completion JSON") from exc
    if not isinstance(record, dict) or set(record) != (set(identity) | {"files"}):
        raise ManifestError("Unexpected completion schema")
    if any(record.get(key) != val for key, val in identity.items()):
        raise ManifestError("Completion identity/fingerprint mismatch")
    files = record.get("files")
    if not isinstance(files, dict) or sorted(files) != paths:
        raise ManifestError("Missing, unexpected or duplicate output entries")
    for name in paths:
        expected = files.get(name)
        if not isinstance(expected, dict) or set(expected) != {"bytes", "sha256"}:
            raise ManifestError("Malformed output entry")
        if not isinstance(expected["bytes"], int) or expected["bytes"] <= 0 or not _hex64(expected["sha256"]):
            raise ManifestError("Invalid artifact fingerprint")
        if _hash(_file(folder, name)) != expected:
            raise ManifestError("Required output changed since publication: " + name)
    return True
