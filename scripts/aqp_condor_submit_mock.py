#!/usr/bin/env python3
"""Reproduce an ambiguous condor_submit acknowledgment with installed MG5 code.

READ ONLY: extracts CondorCluster.submit/submit2 and misc.multiple_try via AST,
then uses in-memory fake subprocesses. No calls to Condor, sleeping, or writes.

An accepted submission with a lost acknowledgment is possible in a real
distributed system. This simulation does NOT prove any historical AQP job
was duplicated for that reason.
"""
import argparse
import ast
import copy
import hashlib
import os
from pathlib import Path
import re
import subprocess
from types import SimpleNamespace
import traceback

ATLAS_CLUSTER_HASH = "feb07ff8af81eb5524ee810d6f4976502457fdf45106a9e2702d1ea46b7ef7fe"
ATLAS_MISC_HASH = "000fee5201091e7f74083f64f2f269f36adf89d8697e4d9c936cc42e5efa122e"


class MockClusterError(Exception):
    pass


class FakeCompletedSubmission:
    def __init__(self, stdout, code=0):
        self.stdout_data = stdout
        self.returncode = code

    def communicate(self, stdin=None):
        return self.stdout_data, b""


def get_method(source, method_name, env, expect_retry=True):
    tree = ast.parse(source)
    classes = [c for c in tree.body if isinstance(c, ast.ClassDef)
               and c.name == "CondorCluster"]
    if len(classes) != 1:
        raise ValueError("CondorCluster not found uniquely")
    candidates = [m for m in classes[0].body if isinstance(m, ast.FunctionDef)
                  and m.name == method_name]
    if len(candidates) != 1:
        raise ValueError("Cannot locate method " + method_name)
    method = copy.deepcopy(candidates[0])
    has_retry = any((isinstance(d, ast.Call) and isinstance(d.func, ast.Name)
                     and d.func.id == "multiple_try") for d in method.decorator_list)
    if has_retry != expect_retry:
        raise ValueError(method_name + ": unexpected automatic retry decoration")
    method.decorator_list = []
    module = ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[]))
    exec(compile(module, "<pinned MG CondorCluster>", "exec"), env)
    return env[method_name]


def get_retry_decorator(source):
    tree = ast.parse(source)
    candidates = [m for m in tree.body if isinstance(m, ast.FunctionDef)
                  and m.name == "multiple_try"]
    if len(candidates) != 1:
        raise ValueError("No unique multiple_try in installed misc.py")
    node = copy.deepcopy(candidates[0])
    node.decorator_list = []
    silence = SimpleNamespace(info=lambda *a: None, debug=lambda *a: None)
    env = {"wait_once": False, "logger": silence, "logger_stderr": silence,
           "time": SimpleNamespace(sleep=lambda n: None), "traceback": traceback}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                 "<pinned MG multiple_try>", "exec"), env)
    return env["multiple_try"]


def attempt(method, cluster_source, misc_source, responses, candidate=False):
    issued = []

    def popen(argv, *args, **kwargs):
        if argv != ["condor_submit"]:
            raise AssertionError("Unexpected external command: " + str(argv))
        index = len(issued)
        if index >= len(responses):
            raise AssertionError("Unexpected submission attempt")
        # Mock scheduler ACCEPTS this job even when acknowledgment is absent.
        issued.append(str(910001 + index))
        return FakeCompletedSubmission(responses[index][0], responses[index][1])

    env = {"os": os, "re": re, "ClusterManagmentError": MockClusterError,
           "subprocess": SimpleNamespace(PIPE=subprocess.PIPE, Popen=popen),
           "misc": SimpleNamespace(Popen=popen)}
    bare = get_method(cluster_source, method, env, expect_retry=not candidate)
    wrapped = bare if candidate else get_retry_decorator(misc_source)()(bare)
    stub = SimpleNamespace(cluster_queue=None, options={},
                           submitted=0, submitted_ids=[])
    kwargs = {"prog": "/bin/true", "cwd": "/tmp"}
    if method == "submit2":
        kwargs["input_files"] = ["fake_input.dat"]
    error = None
    try:
        result = wrapped(stub, **kwargs)
    except MockClusterError as exc:
        if not candidate:
            raise
        result = None
        error = str(exc)
    return {"method": method, "attempts": len(issued),
            "simulated_accepted_ids": issued,
            "tracked_ids": list(stub.submitted_ids),
            "return_value": result, "error": error}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--mg-root", type=Path, help="Original installed MG root")
    source.add_argument("--cluster-file", type=Path, help="Isolated patched cluster.py")
    args = p.parse_args()
    candidate = args.cluster_file is not None
    if candidate:
        cluster = args.cluster_file
        misc_source = None
        if not cluster.is_file() or cluster.name != "cluster.py":
            p.error("Expected isolated cluster.py candidate")
    else:
        cluster = args.mg_root / "madgraph/various/cluster.py"
        misc = args.mg_root / "madgraph/various/misc.py"
        for path, expected in ((cluster, ATLAS_CLUSTER_HASH), (misc, ATLAS_MISC_HASH)):
            if not path.is_file() or sha256(path) != expected:
                p.error("Source hash mismatch at " + str(path))
        misc_source = misc.read_text()
    cluster_source = cluster.read_text()
    print("AQP INTERNAL CONDOR SUBMIT MOCK — NO LIVE SUBMISSIONS")
    for method in ("submit", "submit2"):
        normal = attempt(method, cluster_source, misc_source,
                         [(b"1 job(s) submitted to cluster 910001.\n", 0)],
                         candidate=candidate)
        if normal["attempts"] != 1 or normal["tracked_ids"] != ["910001"]:
            raise RuntimeError(method + ": normal submission fixture failed")
        print(method, "NORMAL_PASS", "attempts=1", "tracked=910001")
        ambiguous = attempt(method, cluster_source, misc_source,
                            [(b"Submitting job(s).\n", 0),
                             (b"1 job(s) submitted to cluster 910002.\n", 0)],
                            candidate=candidate)
        if candidate:
            if (ambiguous["attempts"] != 1 or ambiguous["tracked_ids"]
                    or not ambiguous["error"]):
                raise RuntimeError(method + ": ambiguous submission did not fail closed")
            print(method, "AMBIGUOUS_ACK_FAIL_CLOSED", "attempts=1", "tracked=0")
        else:
            if ambiguous["attempts"] != 2 or ambiguous["tracked_ids"] != ["910002"]:
                raise RuntimeError(method + ": ambiguity fixture did not reproduce")
            print(method, "DUPLICATE_RISK_REPRODUCED", "accepted=2", "tracked=1",
                  "orphaned_simulated_id=910001")
        bad_exit = attempt(method, cluster_source, misc_source,
                           [(b"1 job(s) submitted to cluster 910001.\n", 42)],
                           candidate=candidate)
        if candidate:
            if (bad_exit["attempts"] != 1 or bad_exit["tracked_ids"]
                    or not bad_exit["error"]):
                raise RuntimeError(method + ": nonzero exit not rejected")
            print(method, "NONZERO_EXIT_FAIL_CLOSED", "attempts=1", "tracked=0")
        else:
            if bad_exit["attempts"] != 1 or bad_exit["tracked_ids"] != ["910001"]:
                raise RuntimeError(method + ": returncode fixture did not reproduce")
            print(method, "NONZERO_EXIT_IGNORED", "mock_exit=42", "tracked=910001")
    print("Simulation only: no jobs submitted, no sleeps, no process files modified.")


if __name__ == "__main__":
    main()
