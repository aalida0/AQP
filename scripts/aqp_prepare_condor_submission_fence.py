#!/usr/bin/env python3
"""Build isolated, NON-DEPLOYED MG5 Condor submission + history candidates.

Accept only exact source-pinned Wenu process-local combined candidates.
Adds a limited queue/history identity gate; it does NOT implement complete
recovery, certify GF output integrity, approve physics production, modify
existing Wenu processes, or submit any Condor jobs.
"""
import argparse
import ast
import hashlib
from pathlib import Path
import shutil

from aqp_prepare_bundled_condor_patch import BUNDLES, CENTRAL_SHA, build
from aqp_prepare_condor_status_gate import patch_text as add_history_gate

KNOWN = {
    'standard111': '682075381f79c6ad027244a4a2157f6c21b1202ea561fbc40a8fc0d0383a4a2e',
    'delta111': 'b2879ef87fa4f1a4f70a79699b2db6c1025c0770c3828d704a6c19acb5d2d17a',
    'delta221': 'f17032fc4f814bcbff1b878d1f9192832a266f6f453b82827afe4140dc4c8263',
    'delta441_backup': 'a1d0916e8c9a03b2825a87a781077cc85e4f7119cd2a310bc1b9532cefa791c2',
}


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode()).hexdigest()


def patch_text(src):
    tree = ast.parse(src)
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name == 'CondorCluster']
    if len(classes) != 1:
        raise ValueError('Expected one CondorCluster class')
    lines = src.splitlines(keepends=True)
    edits = []
    for name in ('submit', 'submit2'):
        funcs = [n for n in classes[0].body
                 if isinstance(n, ast.FunctionDef) and n.name == name]
        if len(funcs) != 1:
            raise ValueError('Expected one CondorCluster.' + name)
        func = funcs[0]
        pairs = [(i, lines[i].strip()) for i in range(func.lineno - 1, func.end_lineno)]
        def locate(predicate, label):
            indexes = [i for i, value in pairs if predicate(value)]
            if len(indexes) != 1:
                raise ValueError(name + ': expected unique ' + label + ': ' + str(indexes))
            return indexes[0]
        text_i = locate(lambda x: x.startswith('text = """Executable ='), 'submit text')
        call_i = locate(lambda x: x.startswith('a = ') and "['condor_submit']" in x,
                        'condor_submit subprocess')
        ack_i = locate(lambda x: x == 'self.submitted_ids.append(id)',
                       'in-memory cluster ID record')
        dico_i = locate(lambda x: x.startswith('dico = {'), 'submit dictionary')
        if not (text_i < dico_i < call_i < ack_i):
            raise ValueError(name + ': unexpected submit source layout')
        indent = lines[text_i][:len(lines[text_i]) - len(lines[text_i].lstrip())]
        # The original list is saved before MG converts it into a submit string.
        edits.append((text_i, [indent + '_aqp_original_args = tuple(argument)\n']))
        edits.append((call_i, [
            indent + '_aqp_request_id = _aqp_submission_guard.reserve(\n',
            indent + '    prog, _aqp_original_args, cwd)\n',
            indent + "dico['requirement'] += '\\n+AQPRequestId = \"%s\"' % _aqp_request_id\n",
        ]))
        edits.append((ack_i + 1, [
            indent + '_aqp_submission_guard.acknowledge(_aqp_request_id, id)\n',
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
        'from internal import aqp_condor_submission_guard as _aqp_submission_guard\n',
    ]))
    for idx, insertion in sorted(edits, key=lambda edit: edit[0], reverse=True):
        lines[idx:idx] = insertion
    candidate = ''.join(lines)
    compile(candidate, '<isolated candidate cluster.py>', 'exec')
    if candidate.count('_aqp_submission_guard.reserve(') != 2:
        raise ValueError('Missing submit guard on one of two paths')
    if candidate.count('_aqp_submission_guard.acknowledge(') != 2:
        raise ValueError('Missing ACK record on one of two paths')
    if candidate.count('+AQPRequestId =') != 2:
        raise ValueError('Missing ClassAd token on one of two paths')
    return candidate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True, type=Path)
    parser.add_argument('--central', required=True, type=Path)
    parser.add_argument('--outdir', required=True, type=Path,
                        help='Existing empty directory outside CVMFS/production')
    args = parser.parse_args()
    base = args.base.resolve(strict=True)
    central = args.central.resolve(strict=True)
    outdir = args.outdir.resolve(strict=True)
    if not outdir.is_dir() or list(outdir.iterdir()):
        parser.error('Output directory must exist and be empty')
    if (str(outdir).startswith('/cvmfs/') or '/AQP/Wjets/' in str(outdir)
            or '/AQP/Zjets/' in str(outdir)):
        parser.error('Refusing production/CVMFS destination')
    raw = central.read_bytes()
    if digest(raw) != CENTRAL_SHA:
        parser.error('Central ATLAS source SHA256 mismatch')
    candidates = {}
    for name, (source_hash, _) in BUNDLES.items():
        path = base / name / 'PROCNLO_loop_sm-no_b_mass_0/bin/internal/cluster.py'
        source = path.read_bytes()
        if digest(source) != source_hash:
            parser.error(name + ': original bundled source changed')
        prior = build(raw.decode(), source.decode(), name)
        if digest(prior) != KNOWN[name]:
            parser.error(name + ': combined candidate SHA mismatch')
        candidates[name] = add_history_gate(patch_text(prior))
    srcdir = Path(__file__).resolve().parent
    companions = ('aqp_condor_submission_guard.py', 'aqp_condor_intent_ledger.py',
                  'aqp_condor_completion_guard.py')
    for companion in companions:
        if not (srcdir / companion).is_file():
            parser.error('Missing companion ' + companion)
    for name, candidate in candidates.items():
        # Match the actual generated-process import name: internal.cluster.
        # These copies are isolated, NOT imported by production MadGraph.
        destination = outdir / name / 'internal'
        destination.mkdir(parents=True)
        (destination / '__init__.py').write_text('', encoding='utf-8')
        (destination / 'cluster.py').write_text(candidate, encoding='utf-8')
        for companion in companions:
            shutil.copyfile(srcdir / companion, destination / companion)
        print('ISOLATED_CANDIDATE_CREATED', name, digest(candidate), destination)
    print('NOT_INSTALLED_AND_NOT_PRODUCTION_READY')


if __name__ == '__main__':
    main()
