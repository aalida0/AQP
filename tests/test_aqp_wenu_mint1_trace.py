#!/usr/bin/env python3
"""Offline synthetic tests of the read-only MINT1 submission trace."""
import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))
P = SCRIPT_DIR / "aqp_wenu_mint1_trace.py"
spec = importlib.util.spec_from_file_location("aqp_wenu_mint1_trace", P)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class TraceTests(unittest.TestCase):
    def fixture(self, base, log):
        gf = base / "standard111/PROCNLO_loop_sm-no_b_mass_0/SubProcesses/P1_test/GF2.0"
        gf.mkdir(parents=True)
        (gf / "log_MINT1.txt").write_text(
            "Fortran runtime error: Bad real number in item 15 of list input\n")
        logs = base / "standard111/aqp_condor_timing"
        logs.mkdir()
        (logs / "P1_test__GF2.0__step1.log").write_text(log)

    def run_report(self, base):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            mod.report(base)
        return buffer.getvalue()

    def test_sequential_resubmit_after_previous_terminal(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            self.fixture(base, """000 (100.000.000) 08/17 12:00:00 submitted
001 (100.000.000) 08/17 12:01:00 executing
005 (100.000.000) 08/17 12:02:00 terminated
    (1) Normal termination (return value 0)
000 (200.000.000) 08/17 12:03:00 submitted
001 (200.000.000) 08/17 12:04:00 executing
005 (200.000.000) 08/17 12:05:00 terminated
    (1) Normal termination (return value 1)
""")
            result = self.run_report(base)
            self.assertIn("previous_terminated_before_next_submit", result)
            self.assertIn("100.0,200.0", result)
            self.assertIn("rc=1", result)
            self.assertIn("duplicate_logs_by_stage {'1': 1}", result)

    def test_later_submit_before_first_terminal(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            self.fixture(base, """000 (100.0.0) 08/17 12:00:00 submitted
001 (100.0.0) 08/17 12:01:00 executing
000 (200.0.0) 08/17 12:01:30 submitted
001 (200.0.0) 08/17 12:01:40 executing
005 (100.0.0) 08/17 12:02:00 terminated
""")
            result = self.run_report(base)
            self.assertIn("next_submitted_before_previous_terminal", result)

    def test_missing_timing_directory_is_unknown(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.run_report(Path(folder))
            self.assertIn("NO_TIMING_DIRECTORY; evidence unavailable", result)


if __name__ == "__main__":
    unittest.main()
