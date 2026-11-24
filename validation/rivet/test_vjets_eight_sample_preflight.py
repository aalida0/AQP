"""Regression checks for the eight-sample absolute-shape preflight."""
import gzip
import tempfile
import unittest
from pathlib import Path

from aqp_vjets_eight_sample_preflight import SAMPLES, exact_final_paths


class TestEightSamplePreflight(unittest.TestCase):
    def test_eight_distinct_inputs_and_corrected_wenu_d441(self):
        self.assertEqual({k: len(v) for k, v in SAMPLES.items()},
                         {"Zee": 4, "Wenu": 4})
        inputs = [str(p) for samples in SAMPLES.values() for p in samples.values()]
        self.assertEqual(len(inputs), len(set(inputs)))
        self.assertIn("exclude_invalidXS", inputs[-1])
        self.assertTrue(all("v2_nominal_shapes" not in p for p in inputs))

    def test_extract_exact_final_paths_without_alias_rewriting(self):
        data = """BEGIN YODA_HISTO1D_V2 /RAW/MC_ZJETS:LMODE=EL/jet_HT
Path: /RAW/MC_ZJETS:LMODE=EL/jet_HT
END YODA_HISTO1D_V2
BEGIN YODA_SCATTER2D_V2 /MC_ZJETS:LMODE=EL/jet_HT
Path: /MC_ZJETS:LMODE=EL/jet_HT
END YODA_SCATTER2D_V2
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tiny.yoda.gz"
            with gzip.open(path, "wt") as f:
                f.write(data)
            self.assertEqual(exact_final_paths(path),
                             {"/MC_ZJETS:LMODE=EL/jet_HT"})


if __name__ == "__main__":
    unittest.main()
