#!/usr/bin/env python3
"""Make an isolated, SHA256-pinned sitecustomize bootstrap for Wenu Condor v2.

The unmodified bootstrap_v3 expects the SHA256 of the original cluster.py.
Only the expected digest is replaced in a PRIVATE COPY of sitecustomize.py.
All preexisting source files, checks, and failure behavior are preserved.
"""
import argparse
import hashlib
import shutil
from pathlib import Path

PINNED_V1 = "ab60358a273531522835cd64c0f76acaca91faed1d426374ae8c04796ca4ef3c"
PINNED_V2 = "58ea899d2a214a3a64c321a08e9695a6d613b8e13538727c5c76d57018b9fe07"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_bootstrap(source_bootstrap, candidate, target):
    if sha256(candidate) != PINNED_V2:
        raise ValueError("Condor query-v2 candidate SHA256 mismatch")
    if not source_bootstrap.is_dir() or not (source_bootstrap / "sitecustomize.py").is_file():
        raise ValueError("Missing source sitecustomize.py")
    source = source_bootstrap.resolve(strict=True)
    destination = target.resolve(strict=False)
    if destination == source or source in destination.parents:
        raise ValueError("Refusing to modify the original bootstrap")
    if destination.exists():
        raise ValueError("Refusing to overwrite an existing bootstrap")
    original = (source / "sitecustomize.py").read_text()
    # Fail closed if the original bootstrap has changed unexpectedly.
    if original.count(PINNED_V1) != 1:
        raise ValueError("Expected exactly one original Condor candidate SHA256 pin")
    if PINNED_V2 in original:
        raise ValueError("Source bootstrap already references the v2 digest")
    adapted = original.replace(PINNED_V1, PINNED_V2, 1)
    compile(adapted, "sitecustomize.py", "exec")
    shutil.copytree(source, destination)
    (destination / "sitecustomize.py").write_text(adapted)
    if PINNED_V1 in (destination / "sitecustomize.py").read_text():
        raise ValueError("Old candidate pin unexpectedly remains")
    print("WENU_CONDOR_BOOTSTRAP_V2_BUILT", destination)
    print("QUERY_V2_PIN_SHA256", PINNED_V2)
    print("BOOTSTRAP_SHA256", sha256(destination / "sitecustomize.py"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_bootstrap", type=Path)
    parser.add_argument("query_v2_cluster", type=Path)
    parser.add_argument("new_bootstrap", type=Path)
    args = parser.parse_args()
    try:
        make_bootstrap(args.source_bootstrap, args.query_v2_cluster, args.new_bootstrap)
    except (ValueError, OSError, SyntaxError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
