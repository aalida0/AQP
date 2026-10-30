#!/usr/bin/env python3
"""Synthetic tests: active Delta441 is not historical delta441_backup."""
import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(HERE))
SCRIPT = HERE / "aqp_compare_delta441_active_backup.py"
spec = importlib.util.spec_from_file_location("aqp_compare_delta441_active_backup", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class Delta441CompareTests(unittest.TestCase):
    def create_process(self, base, config, bad=False, complete=True):
        folder = (base / config / mod.PROC / "SubProcesses"
                  / "P2_demo" / "GF7.0")
        folder.mkdir(parents=True)
        (folder / "log_MINT1.txt").write_text(
            "Fortran runtime error: Bad real number in item 15 of list input"
            if bad else "MINT1 finished normally\n"
        )
        if complete:
            for item in mod.ARTIFACTS:
                (folder / item).write_text("nonzero")
        return folder

    def capture(self, base):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            mod.audit(base)
        return buffer.getvalue()

    def test_backup_error_not_misattributed_to_active(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.create_process(root, "delta441", bad=False)
            self.create_process(root, "delta441_backup", bad=True)
            output = self.capture(root)
            self.assertIn("ACTIVE_DELTA441", output)
            self.assertIn("HISTORICAL_BACKUP", output)
            self.assertIn("BACKUP_BAD_REAL_ACTIVE_STATES {'NO_BAD_REAL_MARKER': 1}", output)
            self.assertEqual(mod.summarize(root / "delta441" / mod.PROC)[1], set())
            self.assertEqual(len(mod.summarize(root / "delta441_backup" / mod.PROC)[1]), 1)
            self.assertIn("FOUR_REQUIRED_FILES_NONEMPTY 1", output)

    def test_active_problem_cannot_be_hidden_by_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.create_process(root, "delta441", bad=True, complete=False)
            self.create_process(root, "delta441_backup", bad=False)
            output = self.capture(root)
            self.assertIn("ACTIVE_BAD_REAL_ABSENT_FROM_BACKUP 1", output)
            self.assertIn("MISSING_OR_EMPTY_REQUIRED_FILES 1", output)

    def test_missing_active_fails_instead_of_silent_zero(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.create_process(root, "delta441_backup", bad=True)
            with self.assertRaisesRegex(ValueError, "No SubProcesses directory"):
                mod.audit(root)


if __name__ == "__main__":
    unittest.main()
