#!/usr/bin/env python3
"""Add identity-aware status gates to a NON-DEPLOYED submit-fenced cluster.py.

The gate checks a durable ClassAd-backed queue/history identity before the
existing MG5 check_termination path. Output correctness is NOT certified.
"""
import ast


def patch_text(src):
    tree = ast.parse(src)
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name == 'CondorCluster']
    if len(classes) != 1:
        raise ValueError('Expected one CondorCluster')
    lines = src.splitlines(keepends=True)
    edits = []
    for name in ('control', 'control_one_job'):
        methods = [n for n in classes[0].body
                   if isinstance(n, ast.FunctionDef) and n.name == name]
        if len(methods) != 1:
            raise ValueError('Missing status method ' + name)
        f = methods[0]
        pairs = [(i, lines[i].strip()) for i in range(f.lineno-1, f.end_lineno)]
        if name == 'control':
            matches = [i for i, value in pairs
                       if value == 'status = self.check_termination(id)']
            if len(matches) != 1:
                raise ValueError('Expected one check_termination site')
            idx = matches[0]
            indent = lines[idx][:len(lines[idx])-len(lines[idx].lstrip())]
            edits.append((idx, [
                indent + '_aqp_state = _aqp_completion_guard.check(id)\n',
                indent + "if _aqp_state == 'ACTIVE':\n",
                indent + '    run += 1\n',
                indent + '    continue\n',
                indent + "if _aqp_state != 'TERMINATED':\n",
                indent + "    raise ClusterManagmentError('Unresolved Condor completion')\n",
            ]))
            visible_finished = [i for i, value in pairs
                                if value == "elif status != 'C':"]
            if len(visible_finished) != 1:
                raise ValueError('Expected exactly one visible-completion branch')
            idx = visible_finished[0]
            indent = lines[idx][:len(lines[idx]) - len(lines[idx].lstrip())]
            edits.append((idx, [
                indent + "elif status == 'C':\n",
                indent + '    _aqp_visible = _aqp_completion_guard.check(id)\n',
                indent + "    if _aqp_visible == 'ACTIVE':\n",
                indent + '        run += 1\n',
                indent + "    elif _aqp_visible != 'TERMINATED':\n",
                indent + "        raise ClusterManagmentError('Unresolved Condor completion')\n",
            ]))
        else:
            matches = [i for i, value in pairs if value == 'return output']
            if len(matches) != 1:
                raise ValueError('Expected one return output')
            idx = matches[0]
            indent = lines[idx][:len(lines[idx])-len(lines[idx].lstrip())]
            edits.append((idx, [
                indent + "if not output or output == 'C':\n",
                indent + '    _aqp_state = _aqp_completion_guard.check(id)\n',
                indent + "    if _aqp_state == 'ACTIVE':\n",
                indent + "        return 'R'\n",
                indent + "    if _aqp_state == 'TERMINATED':\n",
                indent + "        return 'C'\n",
                indent + "    raise ClusterManagmentError('Unresolved Condor completion')\n",
            ]))
    # MG5 3.5.11 also contains a nested "import sys" in another
    # scheduler backend. Only the TOP-LEVEL import is a valid anchor.
    imports = [
        node.lineno - 1 for node in tree.body
        if isinstance(node, ast.Import)
        and len(node.names) == 1 and node.names[0].name == 'sys'
    ]
    if len(imports) != 1 or lines[imports[0]].strip() != 'import sys':
        raise ValueError('Expected exactly one module-level import sys')
    edits.append((imports[0] + 1, [
        'from internal import aqp_condor_completion_guard as _aqp_completion_guard\n',
    ]))
    for idx, insertion in sorted(edits, key=lambda entry: entry[0], reverse=True):
        lines[idx:idx] = insertion
    candidate = ''.join(lines)
    compile(candidate, '<isolated status-gated cluster.py>', 'exec')
    if candidate.count('_aqp_completion_guard.check(') != 3:
        raise ValueError('Both status methods must verify history')
    return candidate
