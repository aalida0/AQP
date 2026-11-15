#!/usr/bin/env python3
"""Offline smoke tests for the AQP FxFx log comparison (no Rucio)."""
import io
import tarfile
import tempfile
import unittest
from pathlib import Path
from compare_aqp_logs import all_log_paths, load_log, parse_one, summarize, report_table

MOCK = """generate 12:00:00 Py:Athena INFO starting
| 0 | All included processes | 9000 | 9000 | 5000 |
sumOfPosWeights = 700.0
sumOfNegWeights = -300.0
nPosWeights = 4500
nNegWeights = 500
generation wall time: 20000 s
generate 13:20:00 Py:Athena INFO finished
"""

class AQPLogComparisonTests(unittest.TestCase):
    def test_pooled_metrics(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)/'Zee'/'standard111'/'v2'
            folder.mkdir(parents=True)
            (folder/'first.log.generate.txt').write_text(MOCK)
            rows, result = summarize(Path(td))
            r = result[0]
            self.assertEqual(len(rows), 1)
            self.assertEqual(len(result), 8)
            self.assertEqual(r['accepted_events'], 5000)
            self.assertAlmostEqual(r['weighted_nwf'], .3)
            self.assertAlmostEqual(r['unweighted_nwf'], .1)
            self.assertAlmostEqual(r['fxfx_efficiency'], 5000/9000)
            self.assertAlmostEqual(r['gen_wall_s_per_event'], 4)
            self.assertAlmostEqual(r['dilution_approx'], 6.25)
            self.assertIn('Wenu/delta441', report_table(result))


    def test_native_panda_extension(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)/'Zee'/'standard111'/'v2'
            folder.mkdir(parents=True)
            logfile = folder/'user.aalida.53564233._000328.log.generate'
            logfile.write_text(MOCK)
            self.assertEqual(all_log_paths(folder), [logfile])
            rows, results = summarize(Path(td))
            self.assertEqual(len(rows), 1)
            self.assertEqual(results[0]['downloaded_logs'], 1)
            self.assertEqual(results[0]['valid_accepted_logs'], 1)
            self.assertAlmostEqual(results[0]['weighted_nwf'], .3)


    def test_native_compressed_panda_tarball(self):
        """Rucio transfers the tar.gz but names it *.log.generate."""
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)/'Zee'/'standard111'/'v2'
            folder.mkdir(parents=True)
            filename = folder/'user.aalida.53564233._000328.log.generate'
            payload = MOCK.encode()
            with tarfile.open(filename, 'w:gz') as tar:
                info = tarfile.TarInfo('./log.generate')
                info.size = len(payload)
                tar.addfile(info, io.BytesIO(payload))
            self.assertEqual(load_log(filename), MOCK)
            _, results = summarize(Path(td))
            self.assertEqual(results[0]['accepted_events'], 5000)
            self.assertEqual(results[0]['jobs_weighted_nwf'], 1)

    def test_pythia_space_separated_counts(self):
        from compare_aqp_logs import pythia_counts
        line = 'Pythia8 INFO | 0 | All included subprocesses | 9501 9501 5000 | 1.1e-2 |'
        self.assertEqual(pythia_counts(line), (9501, 9501, 5000))

    def test_wrong_size_excluded(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)/'Wenu'/'delta441'/'v3'
            folder.mkdir(parents=True)
            (folder/'bad.log.generate.txt').write_text(MOCK)
            _, result = summarize(Path(td))
            self.assertEqual(result[-1]['downloaded_logs'], 1)
            self.assertEqual(result[-1]['valid_accepted_logs'], 0)
            self.assertIsNone(result[-1]['weighted_nwf'])

    def test_panda_tarball(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)/'test.log.tgz'
            data = MOCK.encode()
            with tarfile.open(path, 'w:gz') as archive:
                member = tarfile.TarInfo('run/payload.stdout')
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
            self.assertEqual(load_log(path), MOCK)
            self.assertEqual(parse_one(path, 'Zee', 'standard111', 'v2', 5000)['accepted'], 5000)

if __name__ == '__main__':
    unittest.main()
