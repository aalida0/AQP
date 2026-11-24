import unittest
from aqp_rivet_fresh_merge import combine

class FreshMergeTests(unittest.TestCase):
    def test_signed_weight_combination(self):
        xs, sw, sw2, n = combine([(100., 20., 80., 10.), (200., 40., 160., 20.)])
        self.assertAlmostEqual(xs, 150.)
        self.assertEqual((sw, sw2, n), (60., 240., 30.))
    def test_nonpositive_total_rejected(self):
        with self.assertRaises(ValueError):
            combine([(100., -20., 80., 10.)])

if __name__ == "__main__":
    unittest.main()
