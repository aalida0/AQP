#!/usr/bin/env python3
"""Mock scheduler failure against exact installed MG5 CondorCluster methods.

Extracts only control and control_one_job using Python AST and removes
their decorators so one deterministic call can be tested. This does
NOT import MadGraph, invoke condor_q/condor_submit, create any process
in the MG tree, edit installed files, or generate physics events.

Exit status 0 means the diagnostic completed (even if BUG_REPRODUCED).
"""
import argparse
import ast
import copy
import contextlib
import io
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace


class ControlledClusterError(Exception):
    pass


def isolated_method(path, name, popen):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    matching = [node for node in tree.body
                if isinstance(node, ast.ClassDef) and node.name == "CondorCluster"]
    if len(matching) != 1:
        raise RuntimeError("Cannot uniquely locate CondorCluster")
    methods = [node for node in matching[0].body
               if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(methods) != 1:
        raise RuntimeError("Cannot uniquely locate CondorCluster." + name)
    isolated = copy.deepcopy(methods[0])
    isolated.decorator_list = []  # No sleeping, retries, or interrupts.
    module = ast.fix_missing_locations(ast.Module(body=[isolated], type_ignores=[]))
    env = {"misc": SimpleNamespace(Popen=popen),
           "subprocess": subprocess, "sys": sys,
           "ClusterManagmentError": ControlledClusterError}
    exec(compile(module, str(path), "exec"), env)
    return env[name]


def exercise(path, method_name):
    children = []

    def fake_popen(*args, **kwargs):
        # Never execute the requested condor_q command.
        child = subprocess.Popen(
            [sys.executable, "-c",
             "import sys; sys.stderr.write('SECMAN:2007 mock failure\\n'); sys.exit(42)"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        children.append(child)
        return child

    tested_method = isolated_method(path, method_name, fake_popen)
    observed = []
    stub = SimpleNamespace(
        submitted_ids=["987654"],
        submitted=1,
        finish=0,
        jobstatus={"0": "U", "1": "I", "2": "R", "3": "X",
                   "4": "C", "5": "H", "6": "E"},
        check_termination=lambda job_id: observed.append(job_id) or "wait",
    )
    warning_text = io.StringIO()
    try:
        with contextlib.redirect_stderr(warning_text):
            try:
                if method_name == "control_one_job":
                    result = tested_method(stub, "987654")
                else:
                    result = tested_method(stub, ".")
                caught = None
            except ControlledClusterError as exc:
                caught = str(exc)
                result = None
    finally:
        for child in children:
            child.wait(timeout=10)
    if not children or any(child.returncode != 42 for child in children):
        raise RuntimeError("The mock subprocess did not exit with 42")
    return {
        "method": method_name,
        "mock_exit_code": 42,
        "raised_cluster_error": caught is not None,
        "result": result,
        "output_checks_invoked": len(observed),
        "warning_observed": "SECMAN:2007" in warning_text.getvalue(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mg-root", type=Path, required=True)
    args = parser.parse_args()
    source = args.mg_root / "madgraph/various/cluster.py"
    if not source.is_file():
        parser.error("Missing " + str(source))
    print("AQP CONDOR_Q STATUS MOCK (NO LIVE SCHEDULER REQUESTS)")
    for method in ("control_one_job", "control"):
        report = exercise(source, method)
        if report["raised_cluster_error"]:
            verdict = "FAIL_CLOSED"
        elif method == "control" and report["output_checks_invoked"]:
            verdict = "BUG_REPRODUCED_FALSE_JOB_DISAPPEARANCE"
        else:
            verdict = "BUG_REPRODUCED_SUPPRESSED_QUERY_FAILURE"
        print(method, verdict,
              "mock_rc=" + str(report["mock_exit_code"]),
              "result=" + repr(report["result"]),
              "output_checks=" + str(report["output_checks_invoked"]),
              "warning=" + str(report["warning_observed"]))
    print("No MG process, Condor query, integration, production file change or patch was made.")


if __name__ == "__main__":
    main()
