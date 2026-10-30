#!/usr/bin/env python3
"""Read-only audit of MG5 generated-process Condor backends.

Compare original per-process bin/internal/cluster.py to the central ATLAS
3.5.11 source. Do not import MadGraph, run Condor, or modify files.
Differences are printed to stdout only; inspect before sharing.
"""
import argparse
import ast
import difflib
import hashlib
from pathlib import Path
import re

CONFIGS = ("standard111", "delta111", "delta221", "delta441_backup")
METHODS = ("submit", "submit2", "control", "control_one_job", "check_termination")
ATLAS_SHA = "feb07ff8af81eb5524ee810d6f4976502457fdf45106a9e2702d1ea46b7ef7fe"


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def method_text(source, cls_name, method_name):
    tree = ast.parse(source)
    classes = [n for n in tree.body
               if isinstance(n, ast.ClassDef) and n.name == cls_name]
    if len(classes) != 1:
        return None
    functions = [n for n in classes[0].body
                 if isinstance(n, ast.FunctionDef) and n.name == method_name]
    if len(functions) != 1:
        return None
    method = functions[0]
    lines = source.splitlines(keepends=True)
    start = min([method.lineno] + [d.lineno for d in method.decorator_list])
    return "".join(lines[start - 1:method.end_lineno])


def signatures(source):
    tree = ast.parse(source)
    nodes = [n for n in tree.body
             if isinstance(n, ast.ClassDef) and n.name == "CondorCluster"]
    if len(nodes) != 1:
        return {}
    found = {}
    for fn in nodes[0].body:
        if not isinstance(fn, ast.FunctionDef) or fn.name not in METHODS:
            continue
        decorators = [ast.unparse(d) for d in fn.decorator_list]
        calls = [ast.unparse(n.func) for n in ast.walk(fn)
                 if isinstance(n, ast.Call)]
        reads_returncode = sum(
            isinstance(n, ast.Attribute) and n.attr == "returncode"
            for n in ast.walk(fn))
        found[fn.name] = {
            "start": fn.lineno,
            "decorators": decorators,
            "uses_communicate": "status.communicate" in calls,
            "returncode_reads": reads_returncode,
            "uses_stderr_read": "status.stderr.read" in calls,
        }
    return found


def run(args):
    atlas = args.atlas_cluster.expanduser().resolve(strict=True)
    if atlas.name != "cluster.py" or not atlas.is_file():
        raise ValueError("Expected central cluster.py")
    atlas_hash = sha256(atlas)
    if atlas_hash != ATLAS_SHA:
        raise ValueError("Unexpected central cluster.py SHA256 " + atlas_hash)
    base = args.base.expanduser().resolve(strict=True)
    reference = atlas.read_text(errors="replace")
    report = {"baseline": atlas_hash}
    print("MG5 BUNDLED CONDOR SOURCE AUDIT (READ ONLY)")
    print("BASELINE", atlas, atlas_hash)
    print("DIFF OUTPUT may include local patches; review before publishing.")
    for cfg in CONFIGS:
        local = base / cfg / "PROCNLO_loop_sm-no_b_mass_0" / "bin/internal/cluster.py"
        print("\n===", cfg, "===")
        if not local.is_file():
            print("ERROR missing", local)
            continue
        fingerprint = sha256(local)
        print("BUNDLED", local, fingerprint)
        source = local.read_text(errors="replace")
        orig_summary = signatures(reference)
        summary = signatures(source)
        print("EXPECTED_INTERNAL_MODULE", "bin/internal/cluster.py")
        for fn in METHODS:
            a = method_text(reference, "CondorCluster", fn)
            b = method_text(source, "CondorCluster", fn)
            if a is None and b is None:
                continue
            print("METHOD", fn, "CHANGED" if a != b else "same",
                  summary.get(fn, {}))
        diffs = list(difflib.unified_diff(
            reference.splitlines(), source.splitlines(),
            fromfile="ATLAS/cluster.py",
            tofile=cfg + "/bin/internal/cluster.py",
            n=args.context, lineterm="",
        ))
        print("DIFF_LINES", len(diffs))
        for line in diffs[:args.max_lines]:
            print(line)
        if len(diffs) > args.max_lines:
            print("DIFF_TRUNCATED", len(diffs) - args.max_lines,
                  "more lines; increase --max-lines if needed")
        report[cfg] = fingerprint
    print("\nINTERPRETATION: This is a file comparison, not runtime import proof.")
    print("The process launcher imports internal.amcatnlo_run_interface,")
    print("but that interface may import internal.cluster or madgraph.various.cluster.")
    print("Do not patch or restart a production process based on this report.")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", type=Path, required=True,
                   help="Root containing standard111, delta111, delta221, delta441_backup")
    p.add_argument("--atlas-cluster", type=Path, required=True,
                   help="Central installed ATLAS madgraph/various/cluster.py")
    p.add_argument("--context", type=int, default=2)
    p.add_argument("--max-lines", type=int, default=90,
                   help="Maximum unified diff lines per configuration")
    args = p.parse_args()
    if args.context < 0 or args.max_lines < 0:
        p.error("Nonnegative --context and --max-lines required")
    try:
        run(args)
    except (OSError, ValueError, SyntaxError) as exc:
        p.error(str(exc))


if __name__ == "__main__":
    main()
