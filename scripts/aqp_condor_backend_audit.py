#!/usr/bin/env python3
"""Read-only static audit of the installed MG5_aMC@NLO HTCondor backend.

Does not import MadGraph, contact HTCondor, modify files or run generators.
The upstream v3.5.11 implementation can inspect Popen.returncode without
calling wait/poll/communicate first: that risks suppressing condor_q errors.

Usage:
    python3 scripts/aqp_condor_backend_audit.py --mg-root /path/to/mg5-install
"""
import argparse
import ast
import hashlib
from pathlib import Path


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for buf in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(buf)
    return h.hexdigest()


def klass(tree, name):
    return next((node for node in tree.body
                 if isinstance(node, ast.ClassDef) and node.name == name), None)


def method(node, name):
    return next((item for item in node.body
                 if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and item.name == name), None) if node else None


def is_status_method(node, names):
    return (isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in names
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "status")


def find_unreaped_returncodes(node):
    """Find direct 'status.returncode' references preceding any reap/poll.

    This is static pattern analysis, not a proof of what the deployed
    scheduler did. It intentionally doesn't claim to handle aliases/branches.
    """
    if not node:
        return []
    reap = sorted(n.lineno for n in ast.walk(node)
                  if is_status_method(n, {"wait", "poll", "communicate"}))
    reads = sorted(n.lineno for n in ast.walk(node)
                   if isinstance(n, ast.Attribute)
                   and n.attr == "returncode"
                   and isinstance(n.value, ast.Name)
                   and n.value.id == "status")
    return [line for line in reads if not any(reaped < line for reaped in reap)]


def has_retry(node):
    if not node:
        return False
    for decor in node.decorator_list:
        func = decor.func if isinstance(decor, ast.Call) else decor
        if isinstance(func, ast.Name) and func.id == "multiple_try":
            return True
    return False


def audit(cluster_path, misc_path):
    cluster_source = cluster_path.read_text(encoding="utf-8")
    misc_source = misc_path.read_text(encoding="utf-8")
    tree = ast.parse(cluster_source, filename=str(cluster_path))
    ast.parse(misc_source, filename=str(misc_path))
    condor = klass(tree, "CondorCluster")
    base = klass(tree, "Cluster")
    if condor is None or base is None:
        raise ValueError("Could not identify expected Cluster / CondorCluster classes")

    findings = []
    for name in ("control", "control_one_job"):
        fun = method(condor, name)
        if fun is None:
            findings.append(("UNKNOWN", name, "method missing; manual version review required"))
            continue
        lines = find_unreaped_returncodes(fun)
        if lines:
            findings.append(("RISK", name,
                             "status.returncode read before wait/poll/communicate at lines "
                             + ", ".join(map(str, lines))))
        else:
            findings.append(("OK_OR_REVIEW", name,
                             "no unreaped status.returncode found by simple AST check"))
        if has_retry(fun):
            findings.append(("INFO", name, "decorated with multiple_try (status-query retry)"))

    for name in ("submit", "submit2"):
        fun = method(condor, name)
        if fun is None:
            findings.append(("UNKNOWN", name, "method missing; manual version review required"))
        elif has_retry(fun):
            findings.append(("RISK", name,
                             "generic multiple_try wraps side-effecting submission; "
                             "verify idempotency under ambiguous acknowledgment"))
        else:
            findings.append(("INFO", name, "no direct multiple_try decoration detected"))

    ch = method(base, "check_termination")
    if ch:
        findings.append(("INFO", "check_termination",
                         "required-output checks and resubmission policy require runtime audit"))
    else:
        findings.append(("UNKNOWN", "check_termination", "not found"))

    print("MG5 INTERNAL HTCONDOR SOURCE AUDIT (READ ONLY)")
    for tag, path in (("cluster.py", cluster_path), ("misc.py", misc_path)):
        print("SOURCE", tag, path, "SHA256", sha256(path))
    for level, location, detail in findings:
        print(f"[{level}] {location}: {detail}")
    print("NOTE: pattern findings are not proof of historical failure or safe patch semantics.")
    return findings


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mg-root", type=Path, required=True,
                   help="Exact installed MG5 root containing madgraph/various/")
    args = p.parse_args()
    cluster = args.mg_root / "madgraph/various/cluster.py"
    misc = args.mg_root / "madgraph/various/misc.py"
    if not cluster.is_file() or not misc.is_file():
        p.error("Expected files not found: %s and %s" % (cluster, misc))
    try:
        audit(cluster, misc)
    except (SyntaxError, ValueError, OSError, UnicodeError) as exc:
        p.error("Cannot statically inspect source: %s" % exc)


if __name__ == "__main__":
    main()
