#!/usr/bin/env python3
"""Safety regression tests for explicitly approved gridpack workspace pruning."""
import json
import os
from pathlib import Path
import tarfile
import tempfile
from types import SimpleNamespace
import unittest

from scripts import prune_gridpack as cleanup


class PruneTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        root = Path(self.t.name)
        self.home = root / 'home'
        self.run = self.home / 'gridpack-work' / 'tests-1jet-999999.abcdef'
        self.outroot = root / 'data' / 'user' / 'NWR' / 'gridpacks'
        self.out = self.outroot / 'tests-1jet-999999' / self.run.name
        self.run.mkdir(parents=True)
        self.out.mkdir(parents=True)
        (self.run / 'guard').mkdir()
        (self.run / 'jo' / '999999').mkdir(parents=True)
        (self.run / 'jo' / '999999' / 'jo.py').write_text('example jo')
        (self.run / 'launch.sh').write_text('example launcher')
        (self.run / 'gridpack_timing.py').write_text('example timer')
        for name in ('generation.log', 'log.generate', 'controller_cpu.txt', 'timing.txt', 'jo.sha256'):
            (self.run / name).write_text('test')
            (self.out / name).write_text('test')
        source = root / 'a.txt'
        source.write_text('payload')
        self.tar = self.out / 'mc_13TeV.FOO.GRID.tar.gz'
        with tarfile.open(self.tar, 'w:gz') as archive:
            archive.add(source, arcname='a.txt')
        (self.out / 'timing_summary.json').write_text(json.dumps({
            'run': str(self.run), 'transform_exit': 0, 'result_exit': 0,
            'worker_accounting_complete': True, 'history_worker_count': 1,
            'worker_job_ids': ['123.0'], 'stages':[{'accounting_complete':True}]
        }))

    def condor(self, args, **kwargs):
        self.assertEqual(args[0], 'condor_q')
        self.assertIn(str(self.run) + os.sep, args[args.index('-constraint') + 1])
        return SimpleNamespace(stdout='[]', returncode=0)

    def validate(self, **kwargs):
        return cleanup.validate(self.run, self.out, self.home, 'user',
                                runner=kwargs.get('runner', self.condor),
                                output_roots=(self.outroot,))

    def test_dry_run_keeps_all_files(self):
        checked = self.validate()
        self.assertEqual(checked[0], self.run)
        self.assertTrue(self.run.is_dir())
        self.assertFalse((self.out / 'provenance').exists())

    def test_guarded_cleanup_preserves_provenance(self):
        r, out, archive, report = self.validate()
        cleanup.snapshot_and_remove(r, out, archive, report)
        self.assertFalse(self.run.exists())
        self.assertTrue(archive.exists())
        self.assertEqual((out / 'provenance' / 'jo' / '999999' / 'jo.py').read_text(), 'example jo')
        self.assertTrue((out / 'provenance' / 'cleanup_manifest.json').is_file())

    def test_fail_closed_for_active_jobs(self):
        with self.assertRaisesRegex(cleanup.CleanupRefused, 'still active'):
            self.validate(runner=lambda *_, **__: SimpleNamespace(stdout='[{"ClusterId":123}]'))
        self.assertTrue(self.run.exists())

    def test_fail_closed_for_incomplete_accounting(self):
        p = self.out / 'timing_summary.json'
        data = json.loads(p.read_text()); data['worker_accounting_complete'] = False
        p.write_text(json.dumps(data))
        with self.assertRaisesRegex(cleanup.CleanupRefused, 'Incomplete'):
            self.validate()
        self.assertTrue(self.run.exists())

    def test_fail_closed_for_wrong_output(self):
        bad = self.outroot / 'tests-1jet-999999' / 'different_run'
        bad.mkdir()
        with self.assertRaisesRegex(cleanup.CleanupRefused, 'Output must be'):
            cleanup.validate(self.run, bad, self.home, 'user', runner=self.condor,
                             output_roots=(self.outroot,))


if __name__ == '__main__':
    unittest.main()
