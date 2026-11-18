"""Lightweight checks of populated-histogram logic without YODA runtime."""
import importlib.util
import math
import unittest
from pathlib import Path

FILE = Path(__file__).with_name("aqp_wkts_check_yoda.py")
SPEC = importlib.util.spec_from_file_location("wkts_check", FILE)
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


class FakeHistogram:
    def __init__(self, entries, sumw):
        self._entries = entries
        self._sumw = sumw

    def numEntries(self):
        return self._entries

    def sumW(self):
        return self._sumw


class YodaCheckTests(unittest.TestCase):
    def test_populated_histogram(self):
        objects = {
            "/AQP_WKTSPLITTINGS:LMODE=EL/d01": FakeHistogram(200, -1.5),
            "/AQP_WKTSPLITTINGS:LMODE=EL/d12": FakeHistogram(0, 0),
            "/MC_WJETS/test": FakeHistogram(1000, 900),
        }
        self.assertEqual(len(CHECK.inspect(objects)), 2)

    def test_empty_and_nonfinite_histogram_rejected(self):
        with self.assertRaisesRegex(ValueError, "No populated"):
            CHECK.inspect({"/AQP_WKTSPLITTINGS/d01": FakeHistogram(0, 0)})
        with self.assertRaisesRegex(ValueError, "Nonfinite"):
            CHECK.inspect({"/AQP_WKTSPLITTINGS/d01": FakeHistogram(4, math.nan)})


if __name__ == "__main__":
    unittest.main()
