#!/usr/bin/env python3
"""Offline synthetic tests for active/backup Delta441 content audit."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location(
    "aqp_delta441_content_audit", SCRIPTS / "aqp_delta441_content_audit.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class ContentAuditTests(unittest.TestCase):
    def make_gf(self, root, config, channel, gf, grid, bad=False):
        folder = root / config / mod.PROC / "SubProcesses" / channel / gf
        folder.mkdir(parents=True)
        (folder / "mint_grids").write_bytes(grid)
        for f in ("grid.MC_integer", "res.dat", "results.dat"):
            (folder / f).write_bytes(b"baseline")
        (folder / "log_MINT1.txt").write_text(
            "Fortran runtime error: Bad real number in item 15 of list input"
            if bad else "MINT done")
        return folder

    def test_bad_backup_channel_changed_grid_but_other_files_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_gf(root, "delta441_backup", "P2_foo", "GF1.0", b"OLD", bad=True)
            self.make_gf(root, "delta441", "P2_foo", "GF1.0", b"NEWGRID")
            result = mod.compare(root)
            self.assertEqual(result["backup_bad_real"], 1)
            self.assertEqual(result["current_gfs"], 1)
            self.assertEqual(result["all"]["mint_grids"]["CHANGED_SIZE"], 1)
            self.assertEqual(result["old_bad"]["res.dat"]["IDENTICAL"], 1)

    def test_same_size_different_grid_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_gf(root, "delta441_backup", "P1_foo", "GF2.0", b"ABCD")
            self.make_gf(root, "delta441", "P1_foo", "GF2.0", b"EFGH")
            result = mod.compare(root)
            self.assertEqual(result["all"]["mint_grids"]["CHANGED_SAME_SIZE"], 1)
            self.assertEqual(result["all"]["res.dat"]["SAME_SIZE_NOT_HASHED"], 1)
            all_result = mod.compare(root, all_artifacts=True)
            self.assertEqual(all_result["all"]["res.dat"]["IDENTICAL"], 1)

    def test_missing_current_file_not_labeled_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_gf(root, "delta441_backup", "P2_foo", "GF1.0", b"OLD", bad=True)
            active = self.make_gf(root, "delta441", "P2_foo", "GF1.0", b"NEW")
            (active / "res.dat").unlink()
            result = mod.compare(root)
            self.assertEqual(result["old_bad"]["res.dat"]["MISSING"], 1)

    def test_missing_current_subprocess_directory_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_gf(root, "delta441_backup", "P2_foo", "GF1.0", b"OLD", bad=True)
            with self.assertRaises(ValueError):
                mod.compare(root)

    def test_no_bad_real_markers_keeps_zero_old_bad(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_gf(root, "delta441_backup", "P1_foo", "GF1.0", b"SAME")
            self.make_gf(root, "delta441", "P1_foo", "GF1.0", b"SAME")
            result = mod.compare(root)
            self.assertEqual(result["old_bad_details"], [])
            self.assertEqual(result["all"]["mint_grids"]["IDENTICAL"], 1)


if __name__ == "__main__":
    unittest.main()
