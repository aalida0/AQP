#!/usr/bin/env python3
"""Synthetic regression tests for Wenu historical Condor event-log triage."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

P = Path(__file__).resolve().parents[1] / 'scripts/aqp_audit_wenu_condor_eventlogs.py'
spec = importlib.util.spec_from_file_location('audit', P)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class EventLogTests(unittest.TestCase):
    def test_one_submit_two_runs_after_eviction(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'log'
            p.write_text("""000 (1234.000.000) 08/17 19:04:01 Submitted
001 (1234.000.000) 08/17 19:05:01 Executing
004 (1234.000.000) 08/17 19:06:01 Evicted
001 (1234.000.000) 08/17 19:07:01 Executing
005 (1234.000.000) 08/17 19:09:01 Terminated
    (1) Normal termination (return value 0)
""")
            result = audit.read_eventlog(p)
            self.assertEqual(result['submit_ids'], ['1234.0'])
            self.assertEqual(result['repeated_execution_ids'], ['1234.0'])
            self.assertEqual(result['counts']['004'], 1)
            self.assertEqual(result['exit_codes'], [0])

    def test_two_distinct_jobs_in_one_timing_log(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'log'
            p.write_text("""000 (1234.0.0) 08/17 19:04:01 Submitted
000 (1235.0.0) 08/17 19:04:02 Submitted
005 (1234.0.0) 08/17 19:05:01 Terminated
    (1) Normal termination (return value 1)
""")
            result = audit.read_eventlog(p)
            self.assertEqual(result['submit_ids'], ['1234.0', '1235.0'])
            self.assertEqual(result['exit_codes'], [1])

    def test_correlate_bad_mint1_with_step1_multiple_submit(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            gf = base / 'standard111/PROCNLO_loop_sm-no_b_mass_0/SubProcesses/P1_foo/GF2.0'
            gf.mkdir(parents=True)
            (gf / 'log_MINT1.txt').write_text(
                'Fortran runtime error: Bad real number in item 15 of list input')
            timing = base / 'standard111/aqp_condor_timing'
            timing.mkdir()
            (timing / 'P1_foo__GF2.0__step1.log').write_text(
                '000 (1.0.0) 08/17 19:04:01 Submitted\n'
                '000 (2.0.0) 08/17 19:04:05 Submitted\n')
            r = audit.assess(base)['standard111']
            self.assertEqual(r['mint1_bad_real_gfs'], 1)
            self.assertEqual(r['bad_real_with_any_step1_log'], 1)
            self.assertEqual(r['duplicate_submission_log_files'], 1)
            self.assertEqual(r['bad_real_with_distinct_submits'][0]
                             ['submitted_job_ids'], ['1.0', '2.0'])

    def test_missing_timing_log_is_unknown_not_zero_jobs(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            gf = base / 'delta441/PROCNLO_loop_sm-no_b_mass_0/SubProcesses/P1_foo/GF7.0'
            gf.mkdir(parents=True)
            (gf / 'log_MINT1.txt').write_text(
                'Fortran runtime error: Bad real number')
            r = audit.assess(base)['delta441']
            self.assertEqual(r['remaining_unmatched_bad_real_count'], 1)
            self.assertFalse(r['timing_dir_exists'])

    def test_limit_oversized_logs(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'log'
            p.write_text('hello')
            previous = audit.MAX_LOG_BYTES
            try:
                audit.MAX_LOG_BYTES = 2
                with self.assertRaises(ValueError):
                    audit.read_eventlog(p)
            finally:
                audit.MAX_LOG_BYTES = previous


if __name__ == '__main__':
    unittest.main()
