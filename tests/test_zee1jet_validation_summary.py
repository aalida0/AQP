"""Unit tests for conservative 1-jet validation statistics."""
import gzip
import math
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.summarize_zee1jet_validation import (
    find_lhe, inspect_lhe, parse_evnt_weight_metadata,
    parse_shower_counters, summarize,
)


def sample_lhe():
    return """<LesHouchesEvents version="3.0">
<header>
<initrwgt><weight id='1001'>MUR1.0_MUF1.0_PDF325100</weight></initrwgt>
</header>
<init></init>
<event>
3  1  1.0  0 0 0
</event>
<event>
3  1  -2.0  0 0 0
</event>
<event>
3  1  3.0  0 0 0
</event>
<event>
3  1  -1.0  0 0 0
</event>
</LesHouchesEvents>
"""


class SummaryTests(unittest.TestCase):
    def test_weighted_negative_fraction_uses_absolute_weight_sums(self):
        with TemporaryDirectory() as root:
            lhe = Path(root) / "events.lhe"
            lhe.write_text(sample_lhe())
            data = inspect_lhe(lhe)
            self.assertEqual(data["lhe_events"], 4)
            self.assertAlmostEqual(data["sum_positive_nominal_abs"], 4)
            self.assertAlmostEqual(data["sum_negative_nominal_abs"], 3)
            self.assertAlmostEqual(data["weighted_lhe_negative_fraction"], 3 / 7)
            self.assertAlmostEqual(data["unweighted_lhe_negative_fraction"], 0.5)
            self.assertAlmostEqual(
                data["weighted_lhe_dilution_1_over_1_minus_2f_squared"], 49)
            self.assertTrue(data["lhe_header_contains_central_pmg_weight_name"])
            self.assertEqual(data["lhe_header_weight_ids_count"], 1)

    def test_compressed_lhe(self):
        with TemporaryDirectory() as root:
            lhe = Path(root) / "events.lhe.gz"
            with gzip.open(lhe, "wt") as handle:
                handle.write(sample_lhe())
            self.assertEqual(find_lhe(Path(root)), lhe)
            self.assertEqual(inspect_lhe(lhe)["lhe_events"], 4)

    def test_never_infer_fxfx_efficiency_from_evnt_or_lhe_counts(self):
        counters, _ = parse_shower_counters(
            "LHE events generated: 5000\nEVNT_EVENTS 1000\n")
        self.assertIsNone(counters["fxfx_matching_efficiency_from_explicit_counters"])
        explicit, _ = parse_shower_counters(
            "Pythia8 INFO events tried: 3000\n"
            "Pythia8 INFO events accepted: 1000\n")
        self.assertAlmostEqual(
            explicit["fxfx_matching_efficiency_from_explicit_counters"], 1/3)

    def test_evnt_metadata_weighted_nwf_and_dilution(self):
        report = parse_evnt_weight_metadata(
            "generate MetaData: sumOfPosWeights = 4.847110e+06\n"
            "generate MetaData: sumOfNegWeights = 9.927816e+05\n"
            "generate MetaData: sumOfPosWeightsNoFilter = 4.847110e+06\n"
            "generate MetaData: sumOfNegWeightsNoFilter = 9.927816e+05\n"
        )
        expected_fraction = 992781.6 / (4847110.0 + 992781.6)
        expected_dilution = 1.0 / (1.0 - 2.0 * expected_fraction)**2
        self.assertAlmostEqual(
            report["weighted_post_fxfx_negative_fraction"],
            expected_fraction, places=12)
        self.assertAlmostEqual(
            report["weighted_post_fxfx_dilution"],
            expected_dilution, places=12)
        self.assertTrue(report["generator_filter_weight_sums_equal"])

    def test_evnt_metadata_missing_is_unknown(self):
        report = parse_evnt_weight_metadata("Pythia8 FxFx\n")
        self.assertIsNone(report["weighted_post_fxfx_negative_fraction"])
        self.assertIsNone(report["generator_filter_weight_sums_equal"])

    def test_evnt_metadata_duplicate_fields_fail_safe(self):
        report = parse_evnt_weight_metadata(
            "MetaData: sumOfPosWeights = 10\n"
            "MetaData: sumOfPosWeights = 12\n"
            "MetaData: sumOfNegWeights = 2\n"
        )
        self.assertIsNone(report["weighted_post_fxfx_negative_fraction"])

    def test_separates_pre_and_post_fxfx_weight_fractions(self):
        with TemporaryDirectory() as root:
            run = Path(root)
            (run / "events.lhe").write_text(sample_lhe())
            (run / "validation_parameters.txt").write_text(
                "maxEvents=2\ntransform_exit=0\n")
            (run / "generation_shower.log").write_text(
                "Pythia8 running\n"
                "Checking whether the following expected weights are in LHE file: "
                "MUR1.0_MUF1.0_PDF325100\n")
            (run / "zee1jet.EVNT.pool.root").write_bytes(b"nonempty")
            (run / "evnt_count_verified.txt").write_text("2\n")
            summary = summarize(run)
            self.assertTrue(summary["transform_exit_zero"])
            self.assertEqual(summary["evnt_count_confirmed_in_validation_wrapper"], 2)
            self.assertTrue(summary["arrange_output_central_pmg_weight_check_passed"])
            self.assertIsNone(summary["post_fxfx_negative_weight_fraction"])
            self.assertEqual(summary["lhe_pre_fxfx"]["lhe_events"], 4)


if __name__ == "__main__":
    unittest.main()
