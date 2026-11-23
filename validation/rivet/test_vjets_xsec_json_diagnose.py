"""Unit tests for saved per-file cross-section JSON diagnostics."""
import importlib.util
from pathlib import Path
import unittest

FILE = Path(__file__).with_name("aqp_vjets_xsec_json_diagnose.py")
SPEC = importlib.util.spec_from_file_location("xsec_diag", FILE)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class JsonAuditTests(unittest.TestCase):
    def test_invalid_xs_and_zero_sumw_stay_visible(self):
        rows = [
            {"source": "a", "xsec_pb": 20000., "sumW": 5., "entries": 1000.},
            {"source": "b", "xsec_pb": 22000., "sumW": 6., "entries": 1000.},
            {"source": "c", "xsec_pb": 0., "sumW": 1., "entries": 1000.},
            {"source": "d", "xsec_pb": 21000., "sumW": 0., "entries": 1000.},
        ]
        report = {"per_file": rows, "summary": [{
            "merged_xsec_pb": 6831.097, "merged_sumW": 12.}]}
        result = MOD.analyze(report)
        self.assertEqual(result["n_valid"], 2)
        self.assertEqual(result["n_excluded"], 2)
        self.assertEqual([v["source"] for v in result["excluded"]], ["c","d"])
        self.assertEqual(result["sumW_all_known_files"], 12.)
        self.assertAlmostEqual(result["sumW_all_over_merged"], 1.)
        self.assertAlmostEqual(result["xs_event_count_weighted_mean_pb"], 21000.)
        self.assertAlmostEqual(result["xs_sumW_weighted_mean_pb"],
                               (20000*5+22000*6)/11)

    def test_negative_weights_retained(self):
        rows = [
            {"source":"a", "xsec_pb":20000., "sumW":20., "entries":1000.},
            {"source":"b", "xsec_pb":21000., "sumW":-1., "entries":1000.},
        ]
        result=MOD.analyze({"per_file": rows, "summary":[{"merged_sumW":19.}]})
        self.assertEqual(result["n_negative_signed_sumW"],1)
        self.assertEqual(result["sumW_all_known_files"],19.)
        self.assertEqual(result["n_excluded"],0)


if __name__ == "__main__":
    unittest.main()
