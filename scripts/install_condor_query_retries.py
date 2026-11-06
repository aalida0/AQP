#!/usr/bin/env python3
"""Safely install bounded query retries in the site's pinned AQP Condor backend.

The existing .condor/cluster.py is site-local and deliberately not in git.
Updates both that file and the SHA256 pin in scripts/gridpack.sh. Does not
touch running controllers or existing MadGraph process directories.
"""
from __future__ import annotations

import argparse
import ast
import datetime
import hashlib
from pathlib import Path
import shutil
import textwrap


ORIGINAL_SHA = "ab60358a273531522835cd64c0f76acaca91faed1d426374ae8c04796ca4ef3c"
MARKER = "AQP_CONDOR_QUERY_RETRY_V4"

REPLACEMENT = textwrap.dedent("""\
def _aqp_query(args):
    # AQP_CONDOR_QUERY_RETRY_V4: tolerate transient scheduler contact loss.
    # Never treat an unsuccessful query as a completed integration job.
    import time as _aqp_time
    transient = (
        'failed to receive remote ad',
        'failed to contact',
        'cannot contact',
        'could not contact',
        'connection refused',
        'connection reset',
        'connection timed out',
        'timed out',
        'timeout',
        'network is unreachable',
        'temporarily unavailable',
        'communication error',
    )
    attempts = 5
    for attempt in range(attempts):
        try:
            result = subprocess.run(args, capture_output=True, text=True,
                                    timeout=45)
        except (OSError, subprocess.TimeoutExpired) as exc:
            error = 'Condor query failed: %s' % exc
            retry = True
        else:
            if result.returncode == 0:
                # A nonempty stderr with exit code 0 can contain mere warnings;
                # callers still strictly validate returned ID/state rows.
                return [line.split() for line in result.stdout.splitlines()
                        if line.strip()]
            error = 'Condor query error: %s %s' % (
                result.returncode, result.stderr.strip())
            message = (result.stderr + '\\n' + result.stdout).lower()
            retry = any(pattern in message for pattern in transient)
        if not retry or attempt == attempts - 1:
            raise ClusterManagmentError(error)
        delay = min(2 ** attempt, 8)
        print('AQP_CONDOR_QUERY_RETRY attempt=%d/%d delay=%ds: %s' %
              (attempt + 1, attempts, delay, error), flush=True)
        _aqp_time.sleep(delay)


""")


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def patch_source(original: str) -> str:
    if MARKER in original:
        raise ValueError("Retry patch already present")
    start_tag = "def _aqp_query(args):\n"
    end_tag = "\ndef _aqp_states(ids):"
    if original.count(start_tag) != 1 or original.count(end_tag) != 1:
        raise ValueError("Unrecognized Condor backend function boundaries")
    start = original.index(start_tag)
    end = original.index(end_tag, start)
    old_query = original[start:end]
    required = (
        "subprocess.run(args, capture_output=True, text=True, timeout=45)",
        "if result.returncode != 0 or result.stderr.strip():",
        "ClusterManagmentError('Condor query error:",
    )
    if not all(token in old_query for token in required):
        raise ValueError("Unrecognized original AQP query implementation")
    modified = original[:start] + REPLACEMENT.rstrip() + "\n\n" + original[end + 1:]
    ast.parse(modified)
    return modified


def prepare(repo: Path):
    patch_path = repo / ".condor" / "cluster.py"
    launcher_path = repo / "scripts" / "gridpack.sh"
    raw = patch_path.read_bytes()
    if digest(raw) != ORIGINAL_SHA:
        raise ValueError("Refusing to patch unknown cluster.py SHA256: " + digest(raw))
    original = raw.decode("utf-8")
    patched = patch_source(original).encode("utf-8")
    original_launcher = launcher_path.read_text(encoding="utf-8")
    if original_launcher.count(ORIGINAL_SHA) != 1:
        raise ValueError("Launcher does not pin the expected original Condor SHA")
    new_sha = digest(patched)
    launcher = original_launcher.replace(ORIGINAL_SHA, new_sha)
    if launcher.count(new_sha) != 1:
        raise ValueError("New launcher pin validation failed")
    return patch_path, launcher_path, patched, launcher, new_sha


def main():
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Verify without changing files")
    mode.add_argument("--apply", action="store_true", help="Back up then apply changes")
    args = ap.parse_args()
    repo = Path(__file__).resolve().parents[1]
    candidate, launcher, patched, launcher_text, new_sha = prepare(repo)
    print("SOURCE_SHA256=" + ORIGINAL_SHA)
    print("PATCHED_SHA256=" + new_sha)
    print("CONDOR_QUERY_RETRY_PATCH_VALID")
    if args.check:
        return
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = repo / ".condor" / "backups" / ("retry-v4-" + stamp)
    backup.mkdir(parents=True, exist_ok=False)
    shutil.copy2(candidate, backup / "cluster.py")
    shutil.copy2(launcher, backup / "gridpack.sh")
    print("BACKUP=" + str(backup))
    candidate.write_bytes(patched)
    launcher.write_text(launcher_text, encoding="utf-8")
    if digest(candidate.read_bytes()) != new_sha:
        raise RuntimeError("Patch installation SHA mismatch")
    print("AQP_CONDOR_RETRY_INSTALLED")
    print("Next: python3 -m py_compile .condor/cluster.py")
    print("Next: git diff -- scripts/gridpack.sh")


if __name__ == "__main__":
    main()
