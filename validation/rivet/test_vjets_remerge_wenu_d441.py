"""Regression tests for guarded, non-destructive Wenu D441 remerge."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

FILE=Path(__file__).with_name("aqp_vjets_remerge_wenu_d441.py")
SPEC=importlib.util.spec_from_file_location("aqp_remerge_d441",FILE)
MOD=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class MergeRepairTests(unittest.TestCase):
    def example(self, tmp):
        source="/data/aalida/AQP_Rivet_full/outputs/Wenu/delta441/v3/yoda/"
        xs=21116.762525986065
        weight=100439127060/1982
        rows=[
            dict(process="Wenu",config="delta441",
                 source=source+f"user.aalida.good{i:04}.yoda.gz",
                 xsec_pb=xs,sumW=weight,entries=1000,error=None)
            for i in range(1982)
        ]
        rows.extend([
            dict(process="Wenu",config="delta441",
                 source=source+"user.aalida.53651999._001393_282ffe59518d.yoda.gz",
                 xsec_pb=-1.0,sumW=-8267115,entries=1000,error=None),
            dict(process="Wenu",config="delta441",
                 source=source+"user.aalida.53651999._001701_90b7be0871e6.yoda.gz",
                 xsec_pb=-1.0,sumW=-1678280,entries=1000,error=None),
        ])
        data={"per_file":rows,"summary":[{
            "process":"Wenu","config":"delta441",
            "n_files_checked":1984,"merged_xsec_pb":6831.097
        }]}
        result=Path(tmp)/"input.json"
        result.write_text(json.dumps(data))
        return result,data

    def test_inclusion_exclusion_and_exact_reconstruction(self):
        with tempfile.TemporaryDirectory() as tmp:
            file,_=self.example(tmp)
            with patch.object(Path,"is_file",return_value=True):
                paths, bad, info=MOD.load_audit(file)
            self.assertEqual(len(paths),1982)
            self.assertEqual(len(bad),2)
            self.assertEqual(info["included_entries"],1982000)
            self.assertAlmostEqual(info["reconstructed_old_xsec_pb"],6831.097116,places=3)
            self.assertAlmostEqual(info["predicted_rivet_equiv_xsec_pb"],
                                   21116.762525986065,places=5)

    def test_unexpected_bad_record_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            file,data=self.example(tmp)
            data["per_file"][-1]["xsec_pb"]=0.0
            file.write_text(json.dumps(data))
            with patch.object(Path,"is_file",return_value=True):
                with self.assertRaises(ValueError):
                    MOD.load_audit(file)

    def test_partial_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            file,data=self.example(tmp)
            data["per_file"].pop()
            file.write_text(json.dumps(data))
            with patch.object(Path,"is_file",return_value=True):
                with self.assertRaisesRegex(ValueError,"1,984"):
                    MOD.load_audit(file)


if __name__=="__main__":
    unittest.main()
