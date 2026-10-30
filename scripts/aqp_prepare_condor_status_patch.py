#!/usr/bin/env python3
"""Prepare a *candidate copy* of the MG5 3.5.11 HTCondor status-query fix.

The input MG5 cluster.py is read-only. By default print a unified diff only.
--write creates a NEW file with exclusive creation: it never overwrites.
Never put --output inside CVMFS or an existing production process.

No MadGraph imports, Condor commands, gridpack access, or event generation.
Only the two CondorCluster status-query methods are changed.
"""
import argparse
import ast
import difflib
import hashlib
from pathlib import Path
import sys

# Exact ATLAS package inspected on UChicago, AthGeneration 23.6.63.
ATLAS_CLUSTER_SHA256 = (
    "feb07ff8af81eb5524ee810d6f4976502457fdf45106a9e2702d1ea46b7ef7fe"
)
OLD_CHECK = [
    "error = status.stderr.read().decode(errors='ignore')",
    "if status.returncode and error:",
    "raise ClusterManagmentError('condor_q returns error: %s' % error)",
    "elif status.returncode:",
    "raise ClusterManagmentError('condor_q fails with status code: %s' % status.returncode)",
    "elif error:",
    'sys.stderr.write("condor_q error (returncode was 0): %s" % error)',
]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def substitute_single(lines, old, replacement, label):
    indexes = [i for i, line in enumerate(lines) if line.strip() == old]
    if len(indexes) != 1:
        raise ValueError("%s: expected one matching line, found %d: %r" %
                         (label, len(indexes), old))
    index = indexes[0]
    indent = lines[index][:len(lines[index]) - len(lines[index].lstrip())]
    lines[index:index + 1] = [indent + row + "\n" for row in replacement]
    return lines


def patch_method(method_text, name):
    lines = method_text.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.strip() == OLD_CHECK[0]]
    if len(starts) != 1:
        raise ValueError("%s: expected one status check, found %d" % (name, len(starts)))
    pos = starts[0]
    original = [line.strip() for line in lines[pos:pos + len(OLD_CHECK)]]
    if original != OLD_CHECK:
        raise ValueError("%s: unexpected original error-check sequence; refuse patch" % name)
    base = lines[pos][:len(lines[pos]) - len(lines[pos].lstrip())]
    replacement = [
        "stdout_data, stderr_data = status.communicate()",
        "error = stderr_data.decode(errors='replace')",
        "if status.returncode != 0:",
        "    raise ClusterManagmentError(",
        "        'condor_q failed with exit status %s: %s' %",
        "        (status.returncode, error))",
        "if error:",
        '    sys.stderr.write("condor_q warning (exit status 0): %s" % error)',
    ]
    lines[pos:pos + len(OLD_CHECK)] = [base + row + "\n" for row in replacement]
    if name == "control_one_job":
        lines = substitute_single(
            lines,
            "return status.stdout.readline().decode(errors='ignore').strip()",
            [
                "output = stdout_data.decode(errors='replace').strip()",
                "if output and (len(output.split()) != 1 or",
                "               output not in self.jobstatus.values()):",
                "    raise ClusterManagmentError(",
                "        'Malformed condor_q single-job response: %r' % output)",
                "return output",
            ],
            name,
        )
    elif name == "control":
        lines = substitute_single(
            lines, "for line in status.stdout:",
            ["for line in stdout_data.splitlines():"], name,
        )
        lines = substitute_single(
            lines, "id, status = line.decode(errors='ignore').strip().split()",
            [
                "parts = line.decode(errors='replace').strip().split()",
                "if (len(parts) != 2 or not parts[0].isdigit() or",
                "        parts[1] not in self.jobstatus):",
                "    raise ClusterManagmentError(",
                "        'Malformed condor_q queue response: %r' % line)",
                "id, status = parts",
            ], name,
        )
    else:
        raise ValueError("Unexpected method: " + name)
    return "".join(lines)


def patch_text(text):
    root = ast.parse(text)
    candidates = [c for c in root.body if isinstance(c, ast.ClassDef)
                  and c.name == "CondorCluster"]
    if len(candidates) != 1:
        raise ValueError("Expected exactly one CondorCluster class")
    cls = candidates[0]
    methods = []
    for name in ("control", "control_one_job"):
        matches = [n for n in cls.body if isinstance(n, ast.FunctionDef)
                   and n.name == name]
        if len(matches) != 1:
            raise ValueError("Expected one CondorCluster." + name)
        methods.append((matches[0].lineno - 1, matches[0].end_lineno, name))
    lines = text.splitlines(keepends=True)
    for start, end, name in sorted(methods, reverse=True):
        lines[start:end] = patch_method("".join(lines[start:end]), name).splitlines(keepends=True)
    result = "".join(lines)
    if result == text:
        raise ValueError("Patch did not change source")
    compile(result, "<candidate cluster.py>", "exec")
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--output", type=Path, help="New candidate path (required with --write)")
    p.add_argument("--write", action="store_true", help="Write a new file only; refuse overwrite")
    args = p.parse_args()
    src = args.source.expanduser().resolve(strict=True)
    if not src.is_file() or src.name != "cluster.py":
        p.error("Expected existing cluster.py source")
    raw = src.read_bytes()
    source_hash = digest(raw)
    if args.write and source_hash != ATLAS_CLUSTER_SHA256:
        p.error("Unsafe write: source SHA256 differs from pinned ATLAS 3.5.11 version: " + source_hash)
    try:
        current = raw.decode("utf-8")
        patched = patch_text(current)
    except (UnicodeError, ValueError, SyntaxError) as exc:
        p.error(str(exc))
    print("SOURCE_SHA256", source_hash)
    print("CANDIDATE_SHA256", digest(patched.encode("utf-8")))
    print("PATCHED_METHODS CondorCluster.control CondorCluster.control_one_job")
    if not args.write:
        print("DRY_RUN_ONLY: no files changed")
        print("".join(difflib.unified_diff(
            current.splitlines(True), patched.splitlines(True),
            fromfile="cluster.py original", tofile="cluster.py candidate",
        )))
        return
    if args.output is None:
        p.error("--write requires --output")
    destination = args.output.expanduser().absolute()
    if destination == src or destination.is_symlink() or destination.exists():
        p.error("Output path may not overwrite any existing file")
    if not destination.parent.is_dir():
        p.error("Output parent directory must already exist")
    if (str(destination).startswith("/cvmfs/") or
            "/Wjets/WENU/" in str(destination) or
            "/Zjets/" in str(destination)):
        p.error("Refusing output in CVMFS or production directory")
    try:
        with destination.open("x", encoding="utf-8") as stream:
            stream.write(patched)
    except OSError as exc:
        p.error(str(exc))
    print("CANDIDATE_CREATED", destination)
    print("Original source was not modified; candidate is NOT installed.")


if __name__ == "__main__":
    main()
