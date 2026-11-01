#!/usr/bin/env python3
"""Audit and optionally remove a completed gridpack workdir (never a running job)."""
import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
from datetime import datetime, timezone


class CleanupRefused(RuntimeError):
    pass


def require(ok, reason):
    if not ok:
        raise CleanupRefused(reason)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def active_jobs(run, user, runner=subprocess.run):
    root = str(run) + os.sep
    prefix = json.dumps(root)
    constraint = ('Owner == ' + json.dumps(user) +
                  f' && (substr(Iwd, 0, {len(root)}) == {prefix}' +
                  f' || substr(Cmd, 0, {len(root)}) == {prefix})')
    p = runner(['condor_q', '-constraint', constraint, '-json',
                '-attributes', 'ClusterId,ProcId,Iwd,Cmd'],
               capture_output=True, text=True, check=True, timeout=60)
    jobs = json.loads(p.stdout)
    require(isinstance(jobs, list), 'Unexpected condor_q response')
    return jobs


def validate(run_arg, out_arg, home, user, runner=subprocess.run, output_roots=None):
    raw = Path(run_arg).expanduser().absolute()
    require(not raw.is_symlink(), 'Run directory is a symbolic link')
    run = raw.resolve(strict=True)
    base = (Path(home).resolve(strict=True) / 'gridpack-work')
    require(run.is_dir() and run.parent == base, 'Run must be an immediate child of ~/gridpack-work')
    require(not os.path.ismount(run), 'Run directory is a mount point')
    require(run.name not in ('.', '..'), 'Invalid run directory name')

    out_raw = Path(out_arg).expanduser().absolute()
    require(not out_raw.is_symlink(), 'Output directory is a symbolic link')
    out = out_raw.resolve(strict=True)
    if output_roots is None:
        output_roots = (Path('/data') / user / 'NWR' / 'gridpacks',
                        Path('/data') / user / 'gridpacks')
    require(out.name == run.name and
            any(out.is_relative_to(root) and out.parent != root for root in output_roots),
            'Output must be a run-specific directory beneath /data/<user>[/NWR]/gridpacks')
    require(out.is_dir(), 'Output directory missing')
    report_path = out / 'timing_summary.json'
    require(report_path.is_file(), 'Missing timing_summary.json')
    report = json.loads(report_path.read_text())
    require(Path(report.get('run', '')).resolve() == run, 'Timing report belongs to a different run')
    require(report.get('transform_exit') == report.get('result_exit') == 0,
            'Gridpack transform or output packaging did not succeed')
    require(report.get('worker_accounting_complete') is True,
            'Incomplete Condor history: preserve workdir')
    ids = report.get('worker_job_ids')
    require(isinstance(ids, list) and ids and len(ids) == len(set(ids)),
            'Missing or repeated job identities in report: rerun timing extractor first')
    require(len(ids) == report.get('history_worker_count'), 'Worker count mismatch')
    require(all(s.get('accounting_complete') for s in report.get('stages', [])),
            'A Condor stage has incomplete accounting')
    require((run / 'jo').is_dir(), 'Original JO directory missing')
    require((run / 'guard').is_dir() and not any((run / 'guard').iterdir()),
            'Condor submission guard is not empty; preserve for investigation')

    required_logs = ('generation.log', 'log.generate', 'controller_cpu.txt', 'timing.txt', 'jo.sha256')
    for name in required_logs:
        src, dst = run / name, out / name
        require(src.is_file() and dst.is_file(), f'Missing preserved {name}')
        require(digest(src) == digest(dst), f'Preserved {name} differs from live workspace')

    gridpacks = list(out.glob('mc_*GRID.tar.gz'))
    require(len(gridpacks) == 1 and gridpacks[0].stat().st_size > 0,
            'Expected one nonempty gridpack archive')
    with tarfile.open(gridpacks[0], mode='r:gz') as archive:
        for member in archive:
            pass  # Check the entire gzip/tar stream; do not extract files.
    require(not active_jobs(run, user, runner), 'Matching Condor jobs still active')
    return run, out, gridpacks[0], report


def snapshot_and_remove(run, out, archive, report):
    # Preserve the exact JO and execution scripts before removing MG process files.
    provenance = out / 'provenance'
    jo_source = run / 'jo'
    jo_copy = provenance / 'jo'
    if jo_copy.exists():
        require(jo_copy.is_dir(), 'Unexpected existing provenance/jo')
    else:
        provenance.mkdir(parents=True, exist_ok=True)
        shutil.copytree(jo_source, jo_copy)
    originals = [p for p in jo_source.rglob('*') if p.is_file()]
    require(all(digest(p) == digest(jo_copy / p.relative_to(jo_source)) for p in originals),
            'JO provenance verification failed')
    for name in ('launch.sh', 'gridpack_timing.py', 'code.sha256'):
        src = run / name
        if src.is_file():
            dst = provenance / name
            if not dst.exists():
                shutil.copy2(src, dst)
            require(digest(src) == digest(dst), f'Code snapshot differs: {name}')
    manifest = {'original_run': str(run), 'output_directory': str(out),
                'gridpack': archive.name, 'gridpack_sha256': digest(archive),
                'worker_count': report['history_worker_count'],
                'cleanup_utc': datetime.now(timezone.utc).isoformat(),
                'note': 'Full MadGraph integration workspace deleted; cannot resume or debug it.'}
    (provenance / 'cleanup_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    # Do not change directories in a shell that currently sits inside this run.
    cwd = Path.cwd().resolve()
    require(cwd != run and not cwd.is_relative_to(run), 'Refusing to delete current working directory')
    # Never cross an unexpected filesystem mount within the run tree.
    if Path('/proc/self/mountinfo').is_file():
        for line in Path('/proc/self/mountinfo').read_text().splitlines():
            components = line.split()
            if len(components) >= 5:
                mount_path = Path(components[4].replace('\\040', ' '))
                require(not mount_path.is_relative_to(run),
                        f'Nested mount point prevents deletion: {mount_path}')
    shutil.rmtree(run)
    print('WORKDIR_REMOVED', run)
    print('GRIDPACK_RETAINED', archive)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('run', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--delete', action='store_true', help='Delete the run AFTER guarded verification and snapshot')
    args = p.parse_args()
    try:
        run, out, archive, report = validate(args.run, args.output, Path.home(), getpass.getuser())
        print('CLEANUP_ELIGIBLE', run)
        print('GRIDPACK', archive)
        print('WORKER_HISTORY', report['history_worker_count'], 'COMPLETE')
        if args.delete:
            snapshot_and_remove(run, out, archive, report)
        else:
            print('DRY_RUN_ONLY (add --delete to remove original run)')
    except (CleanupRefused, OSError, ValueError, subprocess.SubprocessError,
            tarfile.TarError, json.JSONDecodeError) as exc:
        p.exit(2, f'CLEANUP_REFUSED: {exc}\n')


if __name__ == '__main__':
    main()
