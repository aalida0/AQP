#!/usr/bin/env python3
"""Read-only audit of pinned-version MG5 aMC@NLO job-identity and output semantics.

Does NOT import MadGraph, inspect private GF content, query Condor, submit jobs,
or modify production files. Performs structural AST extraction from installed
MG5 controller/cluster sources and records human-reviewable exact snippets.

Output is source evidence, NOT proof that generated processes use this exact
controller version, that output files are correct, or that a patch is deployable.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path

def _source(path, method, parent=None):
    raw = path.read_bytes()
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError("Refusing oversized source")
    text = raw.decode("utf-8")
    root = ast.parse(text, filename=str(path))
    if parent:
        matches = [n for n in root.body if isinstance(n, ast.ClassDef) and n.name == parent]
        if len(matches) != 1:
            raise ValueError("Missing unique source class: " + parent)
        scope = matches[0].body
    else:
        scope = root.body
    matches = [n for n in scope if isinstance(n, ast.FunctionDef) and n.name == method]
    if len(matches) != 1:
        raise ValueError("Missing unique method " + str((parent, method)))
    definition = matches[0]
    lines = text.splitlines()
    body = lines[definition.lineno - 1:definition.end_lineno]
    return {
        "file": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "first_line": definition.lineno,
        "method_lines": body,
    }


def audit(interface, cluster):
    getio = _source(interface, "getIO_ajob", parent="aMCatNLOCmd")
    runall = _source(interface, "run_all_jobs", parent="aMCatNLOCmd")
    store = _source(cluster, "store_input")
    termination = _source(cluster, "check_termination", parent="Cluster")
    source = "\n".join(getio["method_lines"])
    store_text = "\n".join(store["method_lines"])
    run_text = "\n".join(runall["method_lines"])
    issues = {
        "worker_arguments_include_four_fields":
            "job['channel']" in run_text and "job['run_mode']" in run_text
            and "job['split']" in run_text and "integration_step" in run_text,
        "mintmc_F_B_branches_present":
            "args[1] == 'F' or args[1] == 'B'" in source,
        "mintmc_log_MINT_required":
            "log_MINT%s.txt" in source,
        "worker_outputs_derived_from_getIO":
            "return input_files, output_files, required_output" in source,
        "retry_args_conditional_on_nb_retry":
            "if self.nb_retry > 0" in store_text
            and "self.retry_args[id] = args" in store_text,
        "base_check_termination_uses_required_output":
            "args['required_output']" in "\n".join(termination["method_lines"]),
    }
    def targeted(lines, terms, window=2):
        hits = {i for i, line in enumerate(lines)
                if any(term in line for term in terms)}
        keep = set()
        for i in hits:
            keep.update(range(max(0, i - window), min(len(lines), i + window + 1)))
        return [{"offset": i + 1, "text": lines[i]} for i in sorted(keep)]
    out = {
        "audit": "ATLAS_MG_AJOB_SOURCE_CONTRACT_READ_ONLY",
        "source_evidence_only": True,
        "approved_for_worker_patch": False,
        "controller": {"path": getio["file"], "sha256": getio["sha256"],
                       "getIO_ajob_first_line": getio["first_line"],
                       "required_output_snippets": targeted(
                           getio["method_lines"],
                           ("required_output.append", "if args[1]",
                            "return input_files", "if args[3]"))},
        "run_all_jobs": {"first_line": runall["first_line"],
                         "arguments_snippets": targeted(
                             runall["method_lines"],
                             ("arguments=", "self.run_exe(", "integration_step"))},
        "cluster_backend": {"path": store["file"], "sha256": store["sha256"],
                            "store_input_snippets": targeted(
                                store["method_lines"],
                                ("nb_retry", "retry_args", "def deco_f_store"))},
        "observed_flags": issues,
    }
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interface", required=True, type=Path)
    parser.add_argument("--cluster", required=True, type=Path)
    parser.add_argument("--report", type=Path,
                        help="New JSON destination outside physics process trees")
    args = parser.parse_args()
    result = audit(args.interface.resolve(strict=True),
                   args.cluster.resolve(strict=True))
    for name, found in result["observed_flags"].items():
        print("AJOB_SOURCE_FLAG", name, "YES" if found else "NO")
    print("AJOB_INTERFACE_SHA256", result["controller"]["sha256"])
    print("AJOB_CLUSTER_SHA256", result["cluster_backend"]["sha256"])
    if args.report:
        output = args.report.expanduser().absolute()
        if output.exists() or output.is_symlink():
            parser.error("Refusing existing report destination")
        if str(output).startswith("/cvmfs/") or "/AQP/Wjets/" in str(output):
            parser.error("Refusing production/CVMFS destination")
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print("AJOB_CONTROLLER_SOURCE_REPORT", output)
    print("AJOB_OUTPUT_CONTRACT_APPROVED False (review only)")
    return 0 if all(result["observed_flags"].values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
