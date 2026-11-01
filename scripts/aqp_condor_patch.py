#!/usr/bin/env python3
"""Source-pinned, minimal MG5 3.5.11 Condor fix. Creates a NEW candidate only.

Keep existing MadGraph's required_output/check_termination logic. Stop on
ambiguous submission/status; never automatically retry a submission. A durable
write-once reservation blocks duplicate ajob1 calls across process restarts.
Unresolved reservations require MANUAL investigation; never remove one blindly.
Not a production installer, and does not submit or query actual Condor jobs.
"""
import argparse
import ast
import hashlib
import os
from pathlib import Path

# ATLAS 3.5.11 central and four audited historical, timing-instrumented copies.
PINS = {
    'feb07ff8af81eb5524ee810d6f4976502457fdf45106a9e2702d1ea46b7ef7fe',
    '624717e154fd9bbf0cb7398f310a93c7d7f48c8d7c1a88bce46cc76844c9e5fc',
    '10f51467078d72337a0293b09e62d07f68aa6231eae778ef3ec9326ad13d39c0',
    'f2e95e0143ab6a770679aa7f530d54490fe3f42afaddc6480db761326e8ead16',
    '6c6e193d217313d1b1d04cb28915bf05078109cc8f0da65d9c6f9f1a493adf8b',
}

# Inlined in cluster.py: NO extra runtime modules, no custom worker, no manifests.
HELPERS = '''
import hashlib as _aqp_hashlib
import json as _aqp_json

def _aqp_claim(cwd, prog, arguments):
    if os.path.basename(str(prog)) != 'ajob1':
        return None
    root = os.environ.get('AQP_CONDOR_GUARD_DIR')
    if not root or not os.path.isabs(root) or not os.path.isdir(root):
        raise ClusterManagmentError('Set existing AQP_CONDOR_GUARD_DIR before submission')
    if len(arguments) != 4 or str(arguments[3]) not in ('0', '1', '2'):
        raise ClusterManagmentError('Unexpected ajob1 arguments')
    value = [os.path.realpath(cwd), os.path.realpath(prog), list(map(str, arguments))]
    key = _aqp_hashlib.sha256(_aqp_json.dumps(value, sort_keys=True).encode()).hexdigest()
    path = os.path.join(root, key + '.intent')
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise ClusterManagmentError('Existing ajob1 submission intent: ' + path)
    with os.fdopen(fd, 'w') as handle:
        handle.write(_aqp_json.dumps(value) + '\\n')
        handle.flush()
        os.fsync(handle.fileno())
    fd = os.open(root, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return path


def _aqp_output_contract(cwd, prog, required):
    """Preserve strict outputs except legitimate blank reweight summary.

    When MG explicitly disables BOTH reweight_scale and reweight_pdf,
    scale_pdf_dependence.dat is generated but may contain zero bytes.
    Require its existence; still require nonempty LHE and reweight logs.
    Otherwise keep the complete original nonempty-output contract.
    """
    required = list(required)
    name = 'scale_pdf_dependence.dat'
    if (os.path.basename(str(prog)) != 'reweight_xsec_events.local'
            or name not in required or not cwd):
        return required, []
    card = os.path.join(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.realpath(cwd)))), 'Cards', 'run_card.dat')
    flags = {}
    try:
        with open(card) as handle:
            for line in handle:
                row = line.split('#', 1)[0].split('!', 1)[0]
                if '=' not in row:
                    continue
                value, key = row.split('=', 1)
                key = key.strip().lower()
                if key not in ('reweight_scale', 'reweight_pdf'):
                    continue
                if key in flags:
                    return required, []  # Ambiguous card: fail closed.
                values = [v for v in re.split(r'[\\s,]+',
                          value.strip().strip('[]').lower()) if v]
                flags[key] = (bool(values) and all(v in
                              ('false', 'f', '.false.') for v in values))
    except OSError:
        return required, []  # Unreadable card: fail closed.
    if all(flags.get(key, False) for key in ('reweight_scale', 'reweight_pdf')):
        return [item for item in required if item != name], [name]
    return required, []


def _aqp_query(args):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=45)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ClusterManagmentError('Condor query failed: %s' % exc)
    if result.returncode != 0 or result.stderr.strip():
        raise ClusterManagmentError('Condor query error: %s %s' %
                                   (result.returncode, result.stderr.strip()))
    return [line.split() for line in result.stdout.splitlines() if line.strip()]


def _aqp_states(ids):
    if not ids:
        return {}
    ids = [str(x) for x in ids]
    if len(set(ids)) != len(ids) or not all(x.isdigit() for x in ids):
        raise ClusterManagmentError('Invalid or duplicate tracked Condor job IDs')
    def parse(rows, expected):
        found = {}
        for row in rows:
            if (len(row) != 3 or row[0] not in expected or row[1] != '0'
                    or row[2] not in ('0', '1', '2', '4', '6', '7')
                    or row[0] in found):
                raise ClusterManagmentError('Malformed or unexpected condor_q response')
            found[row[0]] = row[2]
        return found
    result = parse(_aqp_query(['condor_q'] + ids +
                              ['-af', 'ClusterId', 'ProcId', 'JobStatus']), set(ids))
    for jid in ids:
        if jid in result:
            continue
        # Missing in the aggregate reply is NOT proof of completion.
        probe = parse(_aqp_query(['condor_q', jid, '-af', 'ClusterId',
                                  'ProcId', 'JobStatus']), {jid})
        if probe:
            result.update(probe)
            continue
        hist = _aqp_query(['condor_history', jid, '-af', 'ClusterId',
                           'ProcId', 'JobStatus', 'ExitCode'])
        if (len(hist) != 1 or len(hist[0]) != 4 or hist[0][:3] !=
                [jid, '0', '4'] or hist[0][3] != '0'):
            raise ClusterManagmentError('No verified successful Condor history for ' + jid)
        result[jid] = 'DONE'
    return result
'''

CONTROL = '''    def control(self, me_dir):
        if not self.submitted_ids:
            return 0, 0, 0, 0
        idle = run = 0
        states = _aqp_states(list(self.submitted_ids))
        for jid, state in states.items():
            if state in ('0', '1'):
                idle += 1
            elif state in ('2', '4', '6', '7'):
                run += 1  # Queue-visible completed jobs still count as outstanding.
            elif state == 'DONE':
                record = self.retry_args.get(jid)
                if record is None:
                    raise ClusterManagmentError('Missing MadGraph output contract')
                for name in record['required_output']:
                    path = os.path.join(record['cwd'], name) if record['cwd'] else name
                    if not os.path.exists(path) or not os.stat(path).st_size:
                        raise ClusterManagmentError('Missing MadGraph output: ' + path)
                for name in record.get('_aqp_exists_only', []):
                    path = os.path.join(record['cwd'], name) if record['cwd'] else name
                    if not os.path.isfile(path):
                        raise ClusterManagmentError('Missing MadGraph output: ' + path)
                outcome = self.check_termination(jid)  # Original MG output handling.
                if outcome == 'wait':
                    run += 1
                elif outcome == 'resubmit':
                    idle += 1
                elif outcome == 'done':
                    if jid in getattr(self, '_aqp_paths', {}):
                        os.unlink(self._aqp_paths.pop(jid))  # Only after verified completion.
                else:
                    raise ClusterManagmentError('Unexpected MadGraph completion: %r' % outcome)
            else:
                raise ClusterManagmentError('Unrecognized Condor state: ' + state)
        return idle, run, self.submitted - (idle + run), 0
'''
ONE = '''    def control_one_job(self, id):
        state = _aqp_states([id])[str(id)]
        return '' if state == 'DONE' else ('R' if state in ('4', '6', '7') else self.jobstatus[state])
'''


def patch_source(source):
    tree = ast.parse(source)
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'CondorCluster']
    if len(classes) != 1:
        raise ValueError('Missing unique CondorCluster')
    cls = classes[0]
    funcs = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    if not all(name in funcs for name in ('submit', 'submit2', 'control', 'control_one_job')):
        raise ValueError('Missing CondorCluster methods')
    imports = [n for n in tree.body if isinstance(n, ast.Import) and
               len(n.names) == 1 and n.names[0].name == 'sys']
    if len(imports) != 1:
        raise ValueError('Missing unique module-level import sys')
    lines = source.splitlines(keepends=True)
    edits = [(imports[0].end_lineno, [HELPERS])]
    for name in ('submit', 'submit2'):
        func = funcs[name]
        decos = [d for d in func.decorator_list if isinstance(d, ast.Call) and
                 isinstance(d.func, ast.Name) and d.func.id == 'multiple_try']
        if len(decos) != 1 or lines[decos[0].lineno - 1].strip() != '@multiple_try()':
            raise ValueError(name + ': missing exact retry decorator')
        edits.append((decos[0].lineno - 1, [] ,1))
        section = [(i, lines[i].strip()) for i in range(func.lineno - 1, func.end_lineno)]
        def find(predicate, label):
            hits = [i for i, row in section if predicate(row)]
            if len(hits) != 1:
                raise ValueError(name + ': missing/ambiguous ' + label)
            return hits[0]
        first = find(lambda t: t.startswith('text = """Executable ='), 'submit template')
        call = find(lambda t: t.startswith('a = ') and "['condor_submit']" in t,
                    'condor_submit subprocess')
        communicate = find(lambda t: t.startswith('output, _ = a.communicate('),
                           'communicate')
        tracked = find(lambda t: t == 'self.submitted += 1', 'submitted counter')
        if not first < call < communicate < tracked:
            raise ValueError(name + ': unexpected original submit layout')
        ind = lines[first][:len(lines[first]) - len(lines[first].lstrip())]
        edits.extend([
            (first, [ind + '_aqp_args = tuple(argument)\n']),
            (call, [ind + '_aqp_path = _aqp_claim(cwd, prog, _aqp_args)\n']),
            (communicate + 1, [ind + 'if a.returncode != 0:\n',
                               ind + "    raise ClusterManagmentError('condor_submit nonzero exit: %s' % a.returncode)\n"]),
            (tracked, [ind + '_aqp_required, _aqp_exists = _aqp_output_contract(cwd, prog, required_output)\n',
                       ind + 'self.retry_args.setdefault(id, dict(cwd=cwd,\n',
                       ind + '    required_output=_aqp_required, nb_submit=nb_submit,\n',
                       ind + '    _aqp_exists_only=_aqp_exists))\n',
                       ind + 'if _aqp_path is not None:\n',
                       ind + '    self.__dict__.setdefault("_aqp_paths", {})[id] = _aqp_path\n']),
        ])
    for name, body in (('control', CONTROL), ('control_one_job', ONE)):
        f = funcs[name]
        # Retry decorators conceal failures: MG misc.py has a bare 'raise'
        # after retry exhaustion. This interface must fail immediately.
        decos = [d for d in f.decorator_list if isinstance(d, ast.Call) and
                 isinstance(d.func, ast.Name) and d.func.id == 'multiple_try']
        if (len(decos) != 1 or
                not lines[decos[0].lineno - 1].strip().startswith('@multiple_try(')):
            raise ValueError(name + ': missing retry decorator')
        edits.append((decos[0].lineno - 1, [], 1))
        edits.append((f.lineno - 1, body.splitlines(keepends=True),
                      f.end_lineno - (f.lineno - 1)))
    # Reverse order so earlier AST coordinates stay correct.
    for change in sorted(edits, key=lambda item: item[0], reverse=True):
        index, replacement = change[:2]
        remove = change[2] if len(change) > 2 else 0
        lines[index:index + remove] = replacement
    result = ''.join(lines)
    compile(result, '<AQP minimal Condor candidate>', 'exec')
    if '_aqp_path = _aqp_claim(cwd, prog, _aqp_args)' not in result:
        raise ValueError('Patch did not add submission fence')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path,
                   help='NEW candidate outside any physics process or CVMFS')
    a = p.parse_args()
    source = a.source.expanduser().resolve(strict=True)
    destination = a.output.expanduser().absolute()
    if source.name != 'cluster.py' or hashlib.sha256(source.read_bytes()).hexdigest() not in PINS:
        p.error('Source must be one of the exact audited MG5 3.5.11 cluster.py versions')
    if (destination.exists() or destination.is_symlink() or
            not destination.parent.is_dir() or
            str(destination).startswith('/cvmfs/') or '/AQP/Wjets/' in str(destination)
            or '/AQP/Zjets/' in str(destination)):
        p.error('Refusing overwrite or candidate inside production')
    result = patch_source(source.read_text(encoding='utf-8'))
    with destination.open('x', encoding='utf-8') as out:
        out.write(result)
    print('MINIMAL_CANDIDATE', destination)
    print('CANDIDATE_SHA256', hashlib.sha256(result.encode()).hexdigest())
    print('NOT_INSTALLED: No jobs or physics integration launched.')


if __name__ == '__main__':
    main()
