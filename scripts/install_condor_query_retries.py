#!/usr/bin/env python3
"""Safely install bounded query retries in the site's pinned AQP Condor backend.

The existing .condor/cluster.py is site-local and deliberately not in git.
Creates an isolated retry backend and a separate launcher. Does not
modify the original production backend, launcher, controllers, or directories.
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


def update_bootstrap_hash(source: str, new_sha: str) -> str:
    """Retarget exactly one site-local bootstrap pin; reject unknown versions."""
    if source.count(ORIGINAL_SHA) != 1:
        raise ValueError("Unexpected AQP sitecustomize candidate SHA pin; inspect before modifying")
    updated = source.replace(ORIGINAL_SHA, new_sha)
    ast.parse(updated)
    return updated


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
    bootstrap_dir = repo / ".condor" / "bootstrap_v3"
    launcher_path = repo / "scripts" / "gridpack.sh"
    if not (bootstrap_dir / "sitecustomize.py").is_file():
        raise ValueError("Original Condor bootstrap not found")
    raw = patch_path.read_bytes()
    if digest(raw) != ORIGINAL_SHA:
        raise ValueError("Refusing to patch unknown cluster.py SHA256: " + digest(raw))
    patched = patch_source(raw.decode("utf-8")).encode("utf-8")
    original_launcher = launcher_path.read_text(encoding="utf-8")
    default_patchroot = 'patchroot="$' '{GP_PATCH_ROOT:-$repo/.condor}"'
    if original_launcher.count(ORIGINAL_SHA) != 1:
        raise ValueError("Original launcher has unexpected Condor SHA pin")
    if original_launcher.count(default_patchroot) != 1:
        raise ValueError("Original launcher has unexpected patch-root setting")
    new_sha = digest(patched)
    alternate_launcher = (
        original_launcher
        .replace(ORIGINAL_SHA, new_sha)
        .replace(default_patchroot, 'patchroot="$' '{GP_PATCH_ROOT:-$repo/.condor/retry_v4}"')
    )
    if (alternate_launcher.count(new_sha) != 1 or
            alternate_launcher.count(".condor/retry_v4") != 1):
        raise ValueError("Alternative launcher pin validation failed")
    stage_dir = repo / ".condor" / "retry_v4"
    alternate_path = repo / "scripts" / "gridpack_retry_v4.sh"
    return patch_path, bootstrap_dir, launcher_path, patched, alternate_launcher, stage_dir, alternate_path, new_sha


def install_staged(prepared):
    (original_patch, original_bootstrap, original_launcher, patched, launcher_text,
     stage_dir, alternate_path, new_sha) = prepared
    if stage_dir.exists() or alternate_path.exists():
        raise FileExistsError("Alternative backend already exists; refusing overwrite")
    stage_dir.mkdir(parents=True, exist_ok=False)
    try:
        shutil.copytree(original_bootstrap, stage_dir / "bootstrap_v3")
        bootstrap_file = stage_dir / "bootstrap_v3" / "sitecustomize.py"
        bootstrap_file.write_text(
            update_bootstrap_hash(bootstrap_file.read_text(encoding="utf-8"), new_sha),
            encoding="utf-8",
        )
        (stage_dir / "cluster.py").write_bytes(patched)
        alternate_path.write_text(launcher_text, encoding="utf-8")
        alternate_path.chmod(original_launcher.stat().st_mode & 0o777)
        if digest((stage_dir / "cluster.py").read_bytes()) != new_sha:
            raise RuntimeError("Staged candidate SHA mismatch")
        ast.parse((stage_dir / "cluster.py").read_text(encoding="utf-8"))
        import subprocess
        subprocess.run(["bash", "-n", str(alternate_path)], check=True)
        if digest(original_patch.read_bytes()) != ORIGINAL_SHA:
            raise RuntimeError("Original Condor backend unexpectedly changed")
    except Exception:
        if alternate_path.is_file():
            alternate_path.unlink()
        shutil.rmtree(stage_dir, ignore_errors=True)
        raise


def main():
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Verify without changing files")
    mode.add_argument("--apply", action="store_true", help="Create isolated patched backend and launcher")
    args = ap.parse_args()
    repo = Path(__file__).resolve().parents[1]
    prepared = prepare(repo)
    (*_, new_sha) = prepared
    print("SOURCE_SHA256=" + ORIGINAL_SHA)
    print("STAGED_SHA256=" + new_sha)
    print("CONDOR_QUERY_RETRY_PATCH_VALID")
    if args.check:
        return
    install_staged(prepared)
    print("AQP_CONDOR_ISOLATED_BACKEND_INSTALLED")
    print("ORIGINAL_UNTOUCHED=" + str(repo / ".condor/cluster.py"))
    print("ORIGINAL_LAUNCHER_UNTOUCHED=" + str(repo / "scripts/gridpack.sh"))
    print("STAGED_BACKEND=" + str(repo / ".condor/retry_v4/cluster.py"))
    print("STAGED_LAUNCHER=" + str(repo / "scripts/gridpack_retry_v4.sh"))


if __name__ == "__main__":
    main()
