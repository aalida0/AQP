#!/usr/bin/env python3
"""Generate a fail-closed Condor submission candidate from pinned ATLAS MG5.

Expected input: original ATLAS 3.5.11 cluster.py or the previously validated
status-query candidate. Only CondorCluster.submit/submit2 are changed.

Avoids automatic retries of an ambiguous condor_submit acknowledgment and
checks subprocess exit status. Does NOT recover an accepted but untracked job.

By default print diff. --write creates a new exclusive file outside
CVMFS/production. Never imports MadGraph or calls HTCondor.
"""
import argparse
import ast
import difflib
import hashlib
from pathlib import Path

SOURCES = {
    "feb07ff8af81eb5524ee810d6f4976502457fdf45106a9e2702d1ea46b7ef7fe":
        "ATLAS_MG3511_ORIGINAL",
    "bbddb6eedd5c68be6070d3cbc8d3efff20d49851f7eb328932e81d3a8cddb6f9":
        "ATLAS_MG3511_STATUS_FIXED",
}

ACK_LINE = "output, _ = a.communicate((text % dico).encode())"
SUBMIT_LINES = {
    "submit": "a = misc.Popen(['condor_submit'], stdout=subprocess.PIPE,",
    "submit2": "a = subprocess.Popen(['condor_submit'], stdout=subprocess.PIPE,",
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def patch_text(src):
    tree = ast.parse(src)
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name == "CondorCluster"]
    if len(classes) != 1:
        raise ValueError("Expected exactly one CondorCluster")
    cls = classes[0]
    lines = src.splitlines(keepends=True)
    edits = []
    for name in ("submit", "submit2"):
        methods = [n for n in cls.body if isinstance(n, ast.FunctionDef)
                   and n.name == name]
        if len(methods) != 1:
            raise ValueError("Expected exactly one CondorCluster.%s" % name)
        method = methods[0]
        retry = [n for n in method.decorator_list
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                 and n.func.id == "multiple_try"]
        if len(retry) != 1 or lines[retry[0].lineno - 1].strip() != "@multiple_try()":
            raise ValueError("%s: unexpected retry decorator" % name)
        edits.append((retry[0].lineno - 1, retry[0].lineno, []))

        start = method.lineno - 1
        end = method.end_lineno
        body = lines[start:end]
        if sum(ACK_LINE in s for s in body) != 1:
            raise ValueError("%s: unexpected submit acknowledgment code" % name)
        if sum(SUBMIT_LINES[name] in s for s in body) != 1:
            raise ValueError("%s: unexpected subprocess call" % name)
        if sum("pat.search(output).groups()[0]" in s for s in body) != 1:
            raise ValueError("%s: unexpected cluster ID parser" % name)
        if sum("self.submitted_ids.append(id)" in s for s in body) != 1:
            raise ValueError("%s: unexpected cluster state update" % name)
        ack = [i for i in range(start, end) if ACK_LINE in lines[i]]
        if len(ack) != 1 or lines[ack[0]].strip() != ACK_LINE:
            raise ValueError("%s: unexpected communicate line" % name)
        base = lines[ack[0]][:len(lines[ack[0]]) -
                             len(lines[ack[0]].lstrip())]
        additions = [
            "if a.returncode != 0:",
            "    raise ClusterManagmentError(",
            "        'condor_submit failed (exit %s); submission status may be '",
            "        'ambiguous. Reconcile before retrying: %s' %",
            "        (a.returncode, output.decode(errors='replace')))",
        ]
        edits.append((ack[0] + 1, ack[0] + 1,
                      [base + row + "\n" for row in additions]))

        # An empty regex group would otherwise become an invalid tracked ID.
        reg = [i for i in range(start, end)
               if lines[i].strip() == "self.submitted += 1"]
        if len(reg) != 1:
            raise ValueError("%s: unexpected state update" % name)
        check = [
            "if not id.isdigit() or int(id) <= 0:",
            "    raise ClusterManagmentError(",
            "        'condor_submit returned invalid cluster ID; manual '",
            "        'reconciliation required: %r' % id)",
        ]
        edits.append((reg[0], reg[0],
                      [base + row + "\n" for row in check]))

    for start, end, replacement in sorted(edits, key=lambda e: e[0], reverse=True):
        lines[start:end] = replacement
    candidate = "".join(lines)
    compile(candidate, "candidate_cluster.py", "exec")
    if candidate == src:
        raise ValueError("No patch applied")
    return candidate


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--output", type=Path, help="New candidate target outside production")
    p.add_argument("--write", action="store_true")
    args = p.parse_args()

    src = args.source.expanduser().resolve(strict=True)
    if not src.is_file() or src.name != "cluster.py":
        p.error("Expected a cluster.py file")
    raw = src.read_bytes()
    fingerprint = sha(raw)
    if fingerprint not in SOURCES:
        p.error("Refusing unrecognized source SHA256 " + fingerprint)
    try:
        candidate = patch_text(raw.decode("utf-8"))
    except (UnicodeError, ValueError, SyntaxError) as exc:
        p.error(str(exc))

    print("SOURCE", SOURCES[fingerprint], fingerprint)
    print("CANDIDATE_SHA256", sha(candidate.encode("utf-8")))
    print("NO_AUTOMATIC_SUBMIT_RETRY; CONDOR_SUBMIT_EXIT_CHECK; TWO_METHOD_CHANGE")
    if not args.write:
        print("DRY_RUN_ONLY")
        print("".join(difflib.unified_diff(
            raw.decode("utf-8").splitlines(True),
            candidate.splitlines(True),
            fromfile="cluster.py before", tofile="cluster.py candidate",
        )))
        return

    if args.output is None:
        p.error("--write requires --output")
    output = args.output.expanduser().absolute()
    if output == src or output.exists() or output.is_symlink():
        p.error("Refusing to overwrite an existing file")
    if not output.parent.is_dir():
        p.error("Output parent does not exist")
    if (str(output).startswith("/cvmfs/") or
            "/Wjets/WENU/" in str(output) or
            "/Zjets/" in str(output)):
        p.error("Refusing to create a candidate in CVMFS or production")
    try:
        with output.open("x", encoding="utf-8") as out:
            out.write(candidate)
    except OSError as exc:
        p.error(str(exc))
    print("CANDIDATE_CREATED", output)
    print("No files in original MadGraph installation were changed.")


if __name__ == "__main__":
    main()
