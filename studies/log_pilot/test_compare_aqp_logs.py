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
            self.assertEqual(r['accepted_events_measured'], 5000)
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
            self.assertEqual(results[0]['usable_logs'], 1)
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
            self.assertEqual(results[0]['accepted_events_measured'], 5000)
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
            self.assertEqual(result[-1]['usable_logs'], 0)
            self.assertIsNone(result[-1]['weighted_nwf'])


    def test_real_atlas_metadata_and_pythia_efficiency_only(self):
        """Observed format has no explicit Pythia tried/accepted count rows."""
        log = """04:43:42 Pythia8               INFO Pythia8 efficiency (nAccepted/nTried %) = 41.7223
04:43:42 MetaData: sumOfPosWeights = 3.519278e+07
04:43:42 MetaData: sumOfNegWeights = 9.827164e+06
04:43:42 MetaData: sumOfSqrWeights = 1.602503e+12
04:43:42 MetaData: sumOfPosWeightsNoFilter = 3.519278e+07
04:43:42 MetaData: sumOfNegWeightsNoFilter = 9.827164e+06
"""
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)/'Zee'/'standard111'/'v2'
            folder.mkdir(parents=True)
            filename = folder/'user.aalida.53564233._000004.log.generate'
            filename.write_text(log)
            rows, summary = summarize(Path(td))
            r = summary[0]
            self.assertIsNone(rows[0]['accepted'])
            self.assertEqual(r['usable_logs'], 1)
            self.assertEqual(r['jobs_weighted_nwf'], 1)
            self.assertEqual(r['jobs_fxfx'], 1)
            self.assertAlmostEqual(r['weighted_nwf'], 9.827164/(35.19278+9.827164))
            self.assertAlmostEqual(r['fxfx_efficiency'], .417223)
            self.assertEqual(r['fxfx_method'], 'harmonic_mean_assumes_equal_accepted_counts')
            self.assertAlmostEqual(r['neff_weight_moments'],
                                   (3.519278e7-9.827164e6)**2 / 1.602503e12)
            self.assertIn('~41.72', report_table(summary))
            self.assertEqual(r['jobs_with_accepted_counts'], 0)
            self.assertIsNone(r['unweighted_nwf'])

    def test_harmonic_mean_not_arithmetic_for_equal_accepted_counts(self):
        from compare_aqp_logs import summarize_efficiency
        rows = [
            {'fxfx_efficiency_reported': .25, 'accepted': None, 'expected_events': 5000},
            {'fxfx_efficiency_reported': .50, 'accepted': None, 'expected_events': 5000},
        ]
        eff, method, covered = summarize_efficiency(rows)
        self.assertAlmostEqual(eff, 2/(4+2))
        self.assertEqual(covered, 2)
        self.assertIn('harmonic', method)

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
