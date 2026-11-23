"""Synthetic fixtures for read-only eight-YODA physics preflight."""
import gzip
import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).with_name("aqp_vjets_physics_preflight.py")
SPEC = importlib.util.spec_from_file_location("aqp_physics_preflight", MODULE)
PREFLIGHT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREFLIGHT)


FIXTURE = """BEGIN YODA_HISTO1D_V2 /RAW/MC_WJETS:LMODE=EL/jet_HT
Path: /RAW/MC_WJETS:LMODE=EL/jet_HT
# xlow xhigh sumw sumw2 numEntries
0 1 12 20 4
END YODA_HISTO1D_V2
BEGIN YODA_HISTO1D_V2 /MC_WJETS:LMODE=EL/jet_HT
Path: /MC_WJETS:LMODE=EL/jet_HT
# xlow xhigh sumw sumw2 numEntries
0 1 12 20 4
END YODA_HISTO1D_V2
BEGIN YODA_ESTIMATE0D_V3 /_XSEC
Path: /_XSEC
# val err+
123 0.2
END YODA_ESTIMATE0D_V3
BEGIN YODA_COUNTER_V2 /RAW/_EVTCOUNT
Path: /RAW/_EVTCOUNT
# sumw numEntries
12 4
END YODA_COUNTER_V2
"""


class PreflightTests(unittest.TestCase):
    def test_good_gzip_metadata_and_full_histogram(self):
        with tempfile.TemporaryDirectory() as temporary:
            file = Path(temporary, "merged.yoda.gz")
            with gzip.open(file, "wt") as fh:
                fh.write(FIXTURE)
            row = PREFLIGHT.scan_yoda(file)
            self.assertIsNone(row["error"])
            self.assertEqual(row["raw_count"], 2)
            self.assertEqual(row["finalized_count"], 2)
            self.assertIn("/MC_WJETS/jet_HT", row["canonical_final_paths"])
            self.assertTrue(any("_XSEC" in item["path"] for item in row["metadata_blocks"]))
            self.assertTrue(any("_EVTCOUNT" in item["path"] for item in row["metadata_blocks"]))

    def test_missing_file_marks_error_without_fake_rates(self):
        row = PREFLIGHT.scan_yoda(Path("/path/that/should/not/exist.yoda.gz"))
        self.assertEqual(row["error"], "FILE_MISSING")
        self.assertEqual(row["metadata_blocks"], [])

    def test_raw_missing_is_blocker(self):
        with tempfile.TemporaryDirectory() as temporary:
            file = Path(temporary, "merged.yoda")
            file.write_text(FIXTURE.replace("BEGIN YODA_HISTO1D_V2 /RAW",
                                            "BEGIN YODA_HISTO1D_V2 /SKIP")
                            .replace("Path: /RAW", "Path: /SKIP")
                            .replace("BEGIN YODA_COUNTER_V2 /SKIP",
                                     "BEGIN YODA_COUNTER_V2 /RAW"))
            row = PREFLIGHT.scan_yoda(file)
            self.assertIsNone(row["error"])  # RAW event counter remains.
            # Old fake file now has no RAW histogram; bookkeeping alone cannot
            # establish correct histo re-finalization.
            self.assertTrue(any("/SKIP/" in p for p in row["canonical_final_paths"]))

    def test_corrected_sample_version_and_no_wrong_seed_v2(self):
        old = Path("/old")
        new = Path("/new")
        path = PREFLIGHT.reference_path("Wenu", "standard111", old, new)
        self.assertEqual(path, new / "Wenu/standard111/v1/merged/Wenu_standard111_v1_full.yoda.gz")
        path = PREFLIGHT.reference_path("Wenu", "delta441", old, new)
        self.assertEqual(path, new / "Wenu/delta441/v3/merged/Wenu_delta441_v3_full.yoda.gz")
        self.assertIn(("Zee", "delta111"), PREFLIGHT.OLD_CROSS_SECTION)


if __name__ == "__main__":
    unittest.main()
