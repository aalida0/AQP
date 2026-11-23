"""Tests for v2 YODA/PanDA task+job XS pairing; no Rivet required."""
import gzip
import importlib.util
import tempfile
import unittest
from pathlib import Path

PATH=Path(__file__).with_name("aqp_vjets_v2_xsec_match.py")
SPEC=importlib.util.spec_from_file_location("aqp_v2match",PATH)
MOD=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


GENLOG = """Total cross section, incl. bias (DO NOT USE): 6.057e+07 pb
Using FxFx cross section recipe: xs = 2.537e+07 / 1.198e+13
MetaData: cross-section (nb)= 2.117e+00
"""


YODA = """BEGIN YODA_HISTO1D_V2 /RAW/MC_ZJETS:LMODE=EL/jet_HT
Path: /RAW/MC_ZJETS:LMODE=EL/jet_HT
0 1 12 20 4
END YODA_HISTO1D_V2
BEGIN YODA_ESTIMATE0D_V3 /RAW/_XSEC
Path: /RAW/_XSEC
1.0 -0.0 0.0
END YODA_ESTIMATE0D_V3
BEGIN YODA_COUNTER_V3 /RAW/_EVTCOUNT
Path: /RAW/_EVTCOUNT
20000 22000 5000
END YODA_COUNTER_V3
"""


class V2MatchTests(unittest.TestCase):
    def test_recipe_conversion(self):
        info, err=MOD.extract_xsec(GENLOG)
        self.assertIsNone(err)
        self.assertEqual(info["xs_pb"],2117.0)
        self.assertAlmostEqual(info["recipe_calculated_nb"],2.537e7/1.198e13*1e6)
        self.assertLess(abs(info["recipe_relative_difference"]),0.01)

    def test_reject_absurd_recipe(self):
        info,err=MOD.extract_xsec(GENLOG.replace("2.117e+00","2.117e+02"))
        self.assertIsNone(info)
        self.assertTrue(err.startswith("XS_RECIPE_MISMATCH"))

    def test_task_job_key_ignores_random_suffix(self):
        a=MOD.job_key("user.aalida.53564233._000004.log.generate")
        b=MOD.job_key("user.aalida.53564233._000004_cfeebd.yoda.gz")
        self.assertEqual(a,b)
        self.assertEqual(a,("53564233",4))

    def test_one_paired_v2_yoda(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            logs=root/"logs"/"Zee"/"standard111"/"v2"
            logs.mkdir(parents=True)
            (logs/"user.aalida.53564233._000004.log.generate").write_text(GENLOG)
            old=root/"old"
            yoda=old/"Zee"/"standard111"/"yoda"/"user.aalida.53564233._000004_random.yoda.gz"
            yoda.parent.mkdir(parents=True)
            with gzip.open(yoda,"wt") as f:
                f.write(YODA)
            result=MOD.survey_sample(root/"logs",old,root/"new","Zee","standard111")
            self.assertEqual(result["n_yoda_files"],1)
            self.assertEqual(result["n_matched"],1)
            self.assertEqual(result["fraction_yoda_covered"],1)
            self.assertEqual(result["matched"][0]["xs_pb"],2117.0)
            self.assertEqual(result["matched"][0]["yoda_accepted_entries"],5000.0)

    def test_missing_xs_metadata_rejected(self):
        result,err=MOD.extract_xsec("Generator xsec 3.1 pb\n")
        self.assertIsNone(result)
        self.assertEqual(err,"MISSING_POST_FXFX_METADATA_OR_RECIPE")


if __name__=="__main__":
    unittest.main()
