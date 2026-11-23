"""Unit tests for read-only generator cross-section evidence survey."""
import gzip
import importlib.util
import io
import tarfile
import tempfile
import unittest
from pathlib import Path

MODULE=Path(__file__).with_name("aqp_vjets_generator_xsec_evidence.py")
SPEC=importlib.util.spec_from_file_location("aqp_xsec_evidence", MODULE)
MOD=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class GeneratorXsecEvidenceTests(unittest.TestCase):
    CONTENT = (
        "a normal generation log line\n"
        "generate 03:02:01 Generator cross section = 2.12E+04 pb\n"
        "generate 03:02:02 Pythia8 sigmaGen = 2.1e-5\n"
        "generate 03:02:03 URL https://atlas/test cross section\n"
    )

    def test_candidate_scan_does_not_certify_numbers(self):
        result = MOD.candidates_from_text(self.CONTENT)
        self.assertEqual(len(result), 2)
        self.assertIn("2.12E+04", result[0][1])
        self.assertIn("sigmaGen", result[1][1])

    def test_plain_text_log(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"abc.log.generate.txt"
            path.write_text(self.CONTENT)
            self.assertEqual(MOD.decode_log(path), self.CONTENT)

    def test_gzip_log_without_gz_suffix(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"abc.log.generate"
            path.write_bytes(gzip.compress(self.CONTENT.encode()))
            self.assertEqual(MOD.decode_log(path), self.CONTENT)

    def test_tarball_log_without_gz_suffix(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"abc.log.generate"
            raw=self.CONTENT.encode()
            with tarfile.open(path, "w:gz") as tf:
                data=tarfile.TarInfo("output/log.generate")
                data.size=len(raw)
                tf.addfile(data, io.BytesIO(raw))
            self.assertEqual(MOD.decode_log(path), self.CONTENT)

    def test_versions_preserved(self):
        versions={(proc,cfg):version for proc,cfg,version in MOD.PLAN}
        self.assertEqual(versions[("Wenu","standard111")], "v1")
        self.assertEqual(versions[("Wenu","delta441")], "v3")
        self.assertEqual(versions[("Zee","delta441")], "v3")
        self.assertEqual(versions[("Zee","delta111")], "v2")

    def test_report_missing_log_transparent(self):
        with tempfile.TemporaryDirectory() as temp:
            report=MOD.build_report(Path(temp))
            self.assertIn("NO LOGS FOUND",report)
            self.assertIn("RAW_XSEC_EVIDENCE_ONLY",report)


if __name__=="__main__":
    unittest.main()
