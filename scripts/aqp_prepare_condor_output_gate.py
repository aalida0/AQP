#!/usr/bin/env python3
"""Add a fail-closed GF artifact manifest gate to isolated MG5 Condor backend.

This is a source-anchored candidate patch, NOT a production installer. Until
the worker publishes manifests and card/source provenance is bound to each
intent, every attempted GF completion must fail closed.
"""
import ast

def patch_text(src):
    tree = ast.parse(src)
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name == "CondorCluster"]
    if len(classes) != 1:
        raise ValueError("Expected unique CondorCluster")
    cls = classes[0]
    if any(isinstance(n, ast.FunctionDef) and n.name == "check_termination"
           for n in cls.body):
        raise ValueError("CondorCluster already overrides check_termination")
    assignments = [n for n in cls.body if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "job_id" for t in n.targets)]
    if len(assignments) != 1:
        raise ValueError("Expected exactly one CondorCluster.job_id assignment")
    imports = [n for n in tree.body if isinstance(n, ast.Import)
               and len(n.names) == 1 and n.names[0].name == "sys"]
    if len(imports) != 1:
        raise ValueError("Expected unique module-level import sys")
    lines = src.splitlines(keepends=True)
    position = assignments[0].end_lineno
    method = [
        "\n",
        "    def check_termination(self, job_id):\n",
        "        # Require scheduler identity + a rehashed, worker-published\n",
        "        # completion manifest BEFORE original MG output handling.\n",
        "        # MG store_input() only populates retry_args when nb_retry > 0.\n",
        "        # The durable submission ACK always carries the output contract.\n",
        "        _aqp_retry = (self.retry_args.get(job_id)\n",
        "                      if hasattr(self, 'retry_args') else None)\n",
        "        _aqp_output_guard.require_verified(job_id, _aqp_retry)\n",
        "        return super(CondorCluster, self).check_termination(job_id)\n",
    ]
    edits = [
        (position, method),
        (imports[0].end_lineno, [
            "from internal import aqp_condor_output_guard as _aqp_output_guard\n",
        ]),
    ]
    for index, insertion in sorted(edits, key=lambda e: e[0], reverse=True):
        lines[index:index] = insertion
    output = "".join(lines)
    compile(output, "<isolated output-gated cluster.py>", "exec")
    if output.count("_aqp_output_guard.require_verified(") != 1:
        raise ValueError("Output completion gate insertion failed")
    return output
