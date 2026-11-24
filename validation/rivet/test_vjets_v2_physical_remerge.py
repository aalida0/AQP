"""Regression tests for safe v2 post-FxFx Rivet XS override preparation."""
import importlib.util
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from aqp_vjets_v2_physical_remerge import prepare


class V2PhysicalRemergeTests(unittest.TestCase):
    def setUp(self):
        rows = [{"task": "123", "job": i, "yoda_file": f"/tmp/test{i}.yoda.gz",
                 "xs_pb": xs, "xs_nb": xs/1000, "yoda_sumW": sw,
                 "yoda_accepted_entries": 1000, "old_dummy_xs_pb": 1.0}
                for i,xs,sw in ((0,2000.,10.), (1,2200.,20.))]
        self.sample = {"sample":"Zee/standard111/v2", "n_yoda_files":2,
                       "n_matched":2, "n_logs_valid_unique":2,
                       "unmatched_yoda":[], "invalid_yoda":[], "invalid_logs":[],
                       "duplicate_log_task_jobs":[], "matched":rows,
                       "paired_rivet_trials_xs_pb":30./(10./2000.+20./2200.)}

    def test_uses_absolute_override(self):
        commands, xs, sw, entries, total = prepare(
            {"samples":[self.sample]}, "Zee/standard111/v2", check_paths=False)
        self.assertEqual(commands, ["/tmp/test0.yoda.gz:=2000", "/tmp/test1.yoda.gz:=2200"])
        self.assertAlmostEqual(xs, 30./(10./2000.+20./2200.))
        self.assertEqual((sw,entries,total),(30.,2000.,2))

    def test_rejects_missing_log_pairs(self):
        self.sample["n_matched"]=1
        with self.assertRaises(ValueError):
            prepare({"samples":[self.sample]}, "Zee/standard111/v2", check_paths=False)

    def test_rejects_duplicate_yoda(self):
        self.sample["matched"][1]["yoda_file"] = "/tmp/test0.yoda.gz"
        with self.assertRaises(ValueError):
            prepare({"samples":[self.sample]}, "Zee/standard111/v2", check_paths=False)

    def test_small_pilot_does_not_skip_full_audit(self):
        commands, xs, sw, entries, total = prepare(
            {"samples":[self.sample]}, "Zee/standard111/v2", limit=1, check_paths=False)
        self.assertEqual((len(commands),xs,sw,entries,total),(1,2000.,10.,1000.,2))


if __name__ == "__main__":
    unittest.main()
