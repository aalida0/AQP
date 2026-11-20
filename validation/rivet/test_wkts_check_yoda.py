"""Dependency-free regression tests for the AQP YODA histogram smoke check."""
import gzip
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

FILE = Path(__file__).with_name("aqp_wkts_check_yoda.py")
SPEC = importlib.util.spec_from_file_location("wkts_check", FILE)
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)

V2 = """BEGIN YODA_HISTO1D_V2 /RAW/AQP_WKTSPLITTINGS:LMODE=EL/d01
Path: /RAW/AQP_WKTSPLITTINGS:LMODE=EL/d01
Type: Histo1D
---
# ID ID sumw sumw2 sumwx sumwx2 numEntries
Total Total -5 9 -1 2 7
# xlow xhigh sumw sumw2 sumwx sumwx2 numEntries
0 1 -2 4 -1 1 3
1 2 0 0 0 0 0
END YODA_HISTO1D_V2
"""
V3 = """BEGIN YODA_HISTO1D_V3 /AQP_WKTSPLITTINGS:LMODE=EL/d02
Path: /AQP_WKTSPLITTINGS:LMODE=EL/d02
Type: Histo1D
---
Edges(A1): [0.0, 1.0]
# sumW sumW2 sumW(A1) sumW2(A1) numEntries
0 0 0 0 0
0 4 1 1 2
0 0 0 0 0
END YODA_HISTO1D_V3
"""


class YodaCheckTests(unittest.TestCase):
    def test_parses_v2_and_v3_and_accepts_signed_cancellation(self):
        rows = CHECK.inspect((V2 + V3).splitlines())
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][1:], (1, 3, -2))
        self.assertEqual(rows[1][1:], (1, 2, 0))

    def test_empty_histogram_rejected(self):
        with self.assertRaisesRegex(ValueError, "No populated"):
            CHECK.inspect(V2.replace("0 1 -2 4 -1 1 3", "0 1 0 0 0 0 0").splitlines())

    def test_nonfinite_sumw_rejected(self):
        with self.assertRaisesRegex(ValueError, "Nonfinite sumW"):
            CHECK.inspect(V2.replace("0 1 -2 4 -1 1 3", "0 1 nan 4 -1 1 3").splitlines())

    def test_scatter_only_not_mistaken_for_entries(self):
        with self.assertRaisesRegex(ValueError, "No AQP_WKTSPLITTINGS histogram"):
            CHECK.inspect("BEGIN YODA_SCATTER2D_V2 /AQP_WKTSPLITTINGS/d01\n"
                          "Path: /AQP_WKTSPLITTINGS/d01\n"
                          "0.5 0.5 0.5 1.5 0.2 0.2\nEND YODA_SCATTER2D_V2\n".splitlines())

    def test_gz_commandline(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "smoke.yoda.gz"
            with gzip.open(path, "wt") as target:
                target.write(V2)
            proc = subprocess.run([sys.executable, str(FILE), str(path)],
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("AQP_WKTS_YODA_POPULATED_PASS=1", proc.stdout)


if __name__ == "__main__":
    unittest.main()
