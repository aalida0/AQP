import unittest
from unittest.mock import patch
from pathlib import Path
import tempfile
from aqp_rivet_fresh_merge import combine, select_inputs, UNAVAILABLE, coverage

class FreshMergeTests(unittest.TestCase):
    def test_signed_weight_combination(self):
        xs, sw, sw2, n = combine([(100., 20., 80., 10.), (200., 40., 160., 20.)])
        self.assertAlmostEqual(xs, 150.)
        self.assertEqual((sw, sw2, n), (60., 240., 30.))
    def test_exact_transfer_exclusion(self):
        sample, evnt = UNAVAILABLE
        data = {"included": [{"evnt": evnt, "entries": 5000},
                            {"evnt": "other.EVNT.pool.root", "entries": 5000}],
                "excluded": []}
        with tempfile.TemporaryDirectory() as tmp, patch(
                "aqp_rivet_fresh_merge.OUT", Path(tmp)):
            selected, excluded = select_inputs(sample, data)
            self.assertEqual(len(selected), 1)
            self.assertEqual(excluded[0]["evnt"], evnt)
            self.assertFalse(coverage(sample, data))
            folder = Path(tmp)/"full"/sample/"yoda"
            folder.mkdir(parents=True)
            (folder/evnt.replace(".EVNT.pool.root", ".yoda.gz")).touch()
            self.assertEqual(len(select_inputs(sample, data)[0]), 2)
            self.assertFalse(coverage(sample, data))

    def test_nonpositive_total_rejected(self):
        with self.assertRaises(ValueError):
            combine([(100., -20., 80., 10.)])

if __name__ == "__main__":
    unittest.main()
