"""Unit tests for the read-only per-file Rivet cross-section tracer."""
import gzip
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import aqp_vjets_physics_preflight as preflight

MODULE = Path(__file__).with_name("aqp_vjets_xsec_per_file.py")
SPEC = importlib.util.spec_from_file_location("aqp_per_file", MODULE)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


YODA_TEMPLATE = """BEGIN YODA_HISTO1D_V2 /RAW/MC_WJETS:LMODE=EL/jet_HT
Path: /RAW/MC_WJETS:LMODE=EL/jet_HT
0 1 3 4 1
END YODA_HISTO1D_V2
BEGIN YODA_ESTIMATE0D_V3 /RAW/_XSEC
Path: /RAW/_XSEC
{xs} -0.01 0.01
END YODA_ESTIMATE0D_V3
BEGIN YODA_COUNTER_V3 /RAW/_EVTCOUNT
Path: /RAW/_EVTCOUNT
{sumw} 4 1
END YODA_COUNTER_V3
"""


def make_yoda(path, xs, sumw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt") as fh:
        fh.write(YODA_TEMPLATE.format(xs=xs, sumw=sumw))


class PerFileXSTests(unittest.TestCase):
    def test_metadata_values_extracted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "one.yoda.gz"
            make_yoda(path, 6831.1, 12.)
            meta = preflight.scan_yoda(path)
            self.assertEqual(MOD.get_first(meta, "_XSEC"), 6831.1)
            self.assertEqual(MOD.get_first(meta, "_EVTCOUNT"), 12.0)

    def test_per_file_median_and_weighted_mean(self):
        with tempfile.TemporaryDirectory() as tmp:
            old, new = Path(tmp) / "old", Path(tmp) / "new"
            merged = new / "Wenu/delta441/v3/merged/Wenu_delta441_v3_full.yoda.gz"
            make_yoda(merged, 6820., 40.)
            folder = new / "Wenu/delta441/v3/yoda"
            make_yoda(folder / "a.yoda.gz", 6000., 10.)
            make_yoda(folder / "b.yoda.gz", 7000., 30.)
            with patch.object(MOD, "TARGETS", (("Wenu", "delta441"),)):
                report, perfile = MOD.inspect(old, new, limit=20)
            self.assertEqual(len(perfile), 2)
            self.assertEqual(report[0]["merged_xsec_pb"], 6820.)
            self.assertEqual(report[0]["sample_xsec_median_pb"], 6500.)
            self.assertEqual(report[0]["sample_xsec_weighted_avg_pb"], 6750.)
            self.assertAlmostEqual(report[0]["sample_xsec_harmonic_proxy_pb"], 6720.)
            self.assertTrue(report[0]["all_files_checked_and_valid"])
            self.assertEqual(report[0]["n_files_checked"], 2)
            with patch.object(MOD, "TARGETS", (("Wenu", "delta441"),)):
                full, _ = MOD.inspect(old, new, limit=0, targets=(("Wenu", "delta441"),))
            self.assertEqual(full[0]["n_files_checked"], 2)
            self.assertAlmostEqual(full[0]["fractional_difference_weighted_vs_merged"],
                                   6750. / 6820. - 1.)


if __name__ == "__main__":
    unittest.main()
