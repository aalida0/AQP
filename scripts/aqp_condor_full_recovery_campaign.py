#!/usr/bin/env python3
"""One OFFLINE AQP Condor recovery campaign: source pins, new regression
suites, four isolated importable candidates, and full-scale fault injection.

NEVER submits real Condor jobs, runs physics or modifies existing Wenu
processes. Exit 2 means the offline campaign passed but production remains
blocked by outstanding output-integrity and live-scheduler gates.
"""
import argparse
import ast
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

CONFIGS = ('standard111', 'delta111', 'delta221', 'delta441_backup')
TESTS = ('test_aqp_condor_submission_fence.py',
         'test_aqp_condor_completion_guard.py',
         'test_aqp_condor_output_manifest.py',
         'test_aqp_condor_output_guard.py',
         'test_aqp_audit_generated_ajob1_worker.py')


def execute(argv, cwd):
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                          check=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--central', type=Path, required=True)
    parser.add_argument('--channels', type=int, default=300)
    parser.add_argument('--rounds', type=int, default=210)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    if not (10 <= args.channels <= 2000 and 14 <= args.rounds <= 5000):
        parser.error('Invalid stress dimensions')
    output = args.report.expanduser().absolute()
    if output.exists() or output.is_symlink():
        parser.error('Report already exists; refusing overwrite')
    if '/AQP/Wjets/' in str(output) or str(output).startswith('/cvmfs/'):
        parser.error('Refusing report in physics process tree')

    summary = {
        'campaign': 'AQP_MG3511_RECOVERY_CANDIDATE_OFFLINE',
        'real_htcondor_calls': 0,
        'production_files_modified': False,
        'candidate_installed': False,
        'production_readiness': 'BLOCKED',
        'generated_worker_contract_audit': None,
        'tests': {},
        'candidate_imports': {},
        'combined_candidate_control_stress': {},
        'old_backend_stress': None,
        'readiness_blockers': [
            'NO_LIVE_SCHEDULER_TEST',
            'NO_WORKER_PUBLISHED_AND_PROVENANCE_BOUND_GF_OUTPUT_MANIFEST',
            'NO_END_TO_END_CONTROLLER_RESTART_RECONCILIATION',
            'NO_ATLAS_JOB_OPTION_DEPLOYMENT_VALIDATION',
        ],
    }
    failed = False
    with tempfile.TemporaryDirectory(prefix='aqp_condor_full_campaign_') as temp:
        scratch = Path(temp)
        for test in TESTS:
            command = [sys.executable, '-m', 'unittest', 'discover',
                       '-s', 'tests', '-p', test, '-v']
            result = execute(command, repo)
            match = re.search(r'Ran (\d+) tests?', result.stderr)
            count = int(match.group(1)) if match else 0
            passed = result.returncode == 0 and count > 0
            summary['tests'][test] = {
                'passed': passed, 'test_count': count,
                'exit_code': result.returncode,
            }
            print('OFFLINE_REGRESSION', test,
                  'PASS' if passed else 'FAIL', 'count=' + str(count))
            if not passed:
                failed = True
                print(result.stderr[-4000:], file=sys.stderr)

        if not failed:
            # Read-only observation of actual generated ajob1 scripts/output
            # layout. This cannot approve any output manifest or worker hook.
            worker_path = scratch / 'generated_worker_audit.json'
            command = [
                sys.executable,
                str(repo / 'scripts/aqp_audit_generated_ajob1_worker.py'),
                '--base', str(args.base),
                '--report', str(worker_path),
            ]
            worker = execute(command, repo)
            if worker.returncode not in (0, 2) or not worker_path.is_file():
                failed = True
                print('WORKER_SOURCE_AUDIT_FAILED', worker.stderr[-3000:],
                      file=sys.stderr)
            else:
                worker_result = json.loads(worker_path.read_text(encoding='utf-8'))
                summary['generated_worker_contract_audit'] = {
                    'worker_contract_approved': False,
                    'configurations': {
                        name: {
                            'channels': item.get('channel_dirs', 0),
                            'ajob1_workers': item.get('channels_with_ajob1', 0),
                            'stage_result_totals': item.get('stage_result_totals', {}),
                            'worker_pattern_counts': item.get('worker_pattern_counts', {}),
                            'unchecked_result_copy_count': item.get('unchecked_result_copy_count', 0),
                        } for name, item in worker_result['configurations'].items()
                    },
                }
                print(worker.stdout[-3000:])

        if not failed:
            staged = scratch / 'isolated'
            staged.mkdir()
            command = [
                sys.executable,
                str(repo / 'scripts/aqp_prepare_condor_submission_fence.py'),
                '--base', str(args.base),
                '--central', str(args.central),
                '--outdir', str(staged),
            ]
            built = execute(command, repo)
            if built.returncode != 0:
                failed = True
                print('CANDIDATE_GENERATION_FAILED',
                      built.stderr[-4000:], file=sys.stderr)
            else:
                for config in CONFIGS:
                    folder = staged / config / 'internal'
                    candidate = folder / 'cluster.py'
                    module_files = sorted(p.name for p in folder.glob('*.py'))
                    try:
                        source = candidate.read_text(encoding='utf-8')
                        ast.parse(source)
                        required = (
                            'aqp_condor_submission_guard.py',
                            'aqp_condor_intent_ledger.py',
                            'aqp_condor_completion_guard.py',
                            'aqp_condor_output_manifest.py',
                            'aqp_condor_output_guard.py',
                            'cluster.py', '__init__.py',
                        )
                        ready = (
                            all(name in module_files for name in required)
                            and source.count('_aqp_submission_guard.reserve(') == 2
                            and source.count('_aqp_submission_guard.acknowledge(') == 2
                            and source.count('_aqp_completion_guard.check(') == 3
                            and source.count('_aqp_output_guard.require_verified(') == 1
                            and source.count('+AQPRequestId =') == 2
                        )
                    except (OSError, SyntaxError) as exc:
                        ready = False
                        print('INVALID_CANDIDATE', config, str(exc),
                              file=sys.stderr)
                    summary['candidate_imports'][config] = {
                        'generated_package_ready_for_import_test': ready,
                        'module_files': module_files,
                    }
                    print('SOURCE_PINNED_CANDIDATE', config,
                          'PASS' if ready else 'FAIL')
                    failed = failed or not ready

        if not failed:
            # Unlike the legacy large stress, exercise the newly COMBINED
            # candidate's exact CondorCluster control method bodies.
            for config in CONFIGS:
                candidate = staged / config / 'internal' / 'cluster.py'
                command = [
                    sys.executable,
                    str(repo / 'scripts/aqp_condor_combined_control_stress.py'),
                    '--candidate', str(candidate),
                    '--channels', str(args.channels),
                    '--rounds', str(args.rounds),
                ]
                combined = execute(command, repo)
                passed = (combined.returncode == 0 and
                          combined.stdout.startswith('COMBINED_CANDIDATE_STATUS_PASS '))
                if passed:
                    payload = json.loads(combined.stdout.split(' ', 1)[1])
                    passed = (payload['simulated_status_opportunities']
                              == args.channels * args.rounds)
                summary['combined_candidate_control_stress'][config] = {
                    'passed': passed,
                    'simulated_status_opportunities':
                        args.channels * args.rounds if passed else 0,
                }
                print('COMBINED_CANDIDATE_CONTROL', config,
                      'PASS' if passed else 'FAIL')
                if not passed:
                    failed = True
                    print('COMBINED_CONTROL_FAILURE', config,
                          combined.stderr[-3500:] or combined.stdout[-3500:],
                          file=sys.stderr)

        if not failed:
            stress_report = scratch / 'old_stress.json'
            command = [
                sys.executable,
                str(repo / 'scripts/aqp_condor_large_stress.py'),
                '--base', str(args.base),
                '--central', str(args.central),
                '--channels', str(args.channels),
                '--rounds', str(args.rounds),
                '--report', str(stress_report),
            ]
            stress = execute(command, repo)
            print(stress.stdout[-3500:])
            if stress.returncode != 2 or not stress_report.is_file():
                failed = True
                print('LARGE_STRESS_FAILED', stress.stderr[-4000:],
                      file=sys.stderr)
            else:
                result = json.loads(stress_report.read_text(encoding='utf-8'))
                summary['old_backend_stress'] = {
                    'guards': result['guards'],
                    'simulated_gf_status_opportunities':
                        result['simulated_gf_status_opportunities'],
                    'simulated_submission_attempts':
                        result['simulated_submission_attempts'],
                    'readiness_gaps': result['unresolved_safety_gaps'],
                }
                if (result['guards'] != 'PASS'
                        or result['production_readiness'] != 'BLOCKED'):
                    failed = True

        summary['offline_candidate_validation'] = (
            'FAIL' if failed else 'PASS'
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('x', encoding='utf-8') as stream:
            json.dump(summary, stream, indent=2, sort_keys=True)
            stream.write('\n')
    print('REPORT', output)
    print('OFFLINE_CANDIDATE_VALIDATION',
          summary['offline_candidate_validation'])
    print('PRODUCTION_READINESS', summary['production_readiness'])
    print('NOTE: no real scheduler; worker manifest publication and restart recovery outstanding')
    return 1 if failed else 2


if __name__ == '__main__':
    sys.exit(main())
