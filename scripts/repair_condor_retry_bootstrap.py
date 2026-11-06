#!/usr/bin/env python3
"""Repair the already staged *isolated* AQP retry bootstrap candidate pin.

Never edits the production Condor backend, its bootstrap or production launcher.
"""
from __future__ import annotations

import ast
from pathlib import Path

from install_condor_query_retries import ORIGINAL_SHA, digest, update_bootstrap_hash

repo = Path(__file__).resolve().parents[1]
staged_dir = repo / ".condor" / "retry_v4"
candidate = staged_dir / "cluster.py"
bootstrap = staged_dir / "bootstrap_v3" / "sitecustomize.py"
original = repo / ".condor" / "bootstrap_v3" / "sitecustomize.py"
prod_backend = repo / ".condor" / "cluster.py"
prod_launcher = repo / "scripts" / "gridpack.sh"
staged_launcher = repo / "scripts" / "gridpack_retry_v4.sh"

if digest(prod_backend.read_bytes()) != ORIGINAL_SHA:
    raise SystemExit("REFUSING: original cluster.py SHA does not match pin")

if original.resolve() == bootstrap.resolve():
    raise SystemExit("REFUSING: bootstrap is not isolated")

staged_sha = digest(candidate.read_bytes())
original_data = original.read_bytes()
original_launcher_data = prod_launcher.read_bytes()
staged_source = candidate.read_text(encoding="utf-8")
if "AQP_CONDOR_QUERY_RETRY_V4" not in staged_source:
    raise SystemExit("REFUSING: staged backend is not the retry version")
if staged_launcher.read_text(encoding="utf-8").count(staged_sha) != 1:
    raise SystemExit("REFUSING: staged launcher candidate pin mismatch")

current = bootstrap.read_text(encoding="utf-8")
if current.count(staged_sha) == 1 and ORIGINAL_SHA not in current:
    print("ISOLATED_BOOTSTRAP_ALREADY_CORRECT", staged_sha)
elif current.count(ORIGINAL_SHA) == 1 and staged_sha not in current:
    patched = update_bootstrap_hash(current, staged_sha)
    bootstrap.write_text(patched, encoding="utf-8")
    print("ISOLATED_BOOTSTRAP_SHA_UPDATED", staged_sha)
else:
    raise SystemExit(
        "REFUSING: unknown sitecustomize pin layout; print SHA-related lines "
        "from .condor/retry_v4/bootstrap_v3/sitecustomize.py for inspection"
    )

ast.parse(bootstrap.read_text(encoding="utf-8"))
assert original.read_bytes() == original_data
assert prod_launcher.read_bytes() == original_launcher_data
print("PRODUCTION_BACKEND_AND_LAUNCHER_UNTOUCHED")
