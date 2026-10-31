#!/usr/bin/env python3
"""Offline corruption/identity tests for the non-production GF manifest contract."""
import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "aqp_condor_output_manifest.py"
spec = importlib.util.spec_from_file_location("aqp_condor_output_manifest", SCRIPT)
manifest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manifest)


class OutputManifestTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.work = self.root / "P2_test" / "GF7.0"
        self.work.mkdir(parents=True)
        self.ledger = self.root / "ledger"
        self.ledger.mkdir()
        self.filename = "res_1.dat"
        (self.work / self.filename).write_bytes(b"integrated grid fixture\n")
        self.kw = dict(request_id="AQP" + "a" * 40, cluster_id="910001",
                       input_sha256=hashlib.sha256(b"source+cards").hexdigest(),
                       process="P2_test", stage="MINT1", gf="GF7.0",
                       required_output=[self.filename])

    def publish(self, **changes):
        params = dict(self.kw, **changes)
        return manifest.publish(self.ledger, self.work, **params)

    def verify(self, **changes):
        params = dict(self.kw, **changes)
        return manifest.verify(self.ledger, self.work, **params)

    def test_publication_and_independent_rehash(self):
        path = self.publish()
        self.assertTrue(path.is_file())
        self.assertTrue(self.verify())

    def test_publication_is_write_once(self):
        path = self.publish()
        first = path.read_bytes()
        with self.assertRaisesRegex(manifest.ManifestError, "already exists"):
            self.publish()
        self.assertEqual(path.read_bytes(), first)

    def test_missing_manifest_is_blocked(self):
        with self.assertRaisesRegex(manifest.ManifestError, "No trusted published"):
            self.verify()

    def test_modified_grid_bytes_are_detected(self):
        self.publish()
        (self.work / self.filename).write_bytes(b"different fake integration grid")
        with self.assertRaisesRegex(manifest.ManifestError, "changed since"):
            self.verify()

    def test_truncated_grid_is_detected(self):
        self.publish()
        (self.work / self.filename).write_bytes(b"")
        with self.assertRaisesRegex(manifest.ManifestError, "empty"):
            self.verify()

    def test_wrong_input_source_identity_is_blocked(self):
        self.publish()
        with self.assertRaisesRegex(manifest.ManifestError, "identity/fingerprint"):
            self.verify(input_sha256="1" * 64)

    def test_wrong_job_id_is_blocked(self):
        self.publish()
        with self.assertRaisesRegex(manifest.ManifestError, "identity/fingerprint"):
            self.verify(cluster_id="910002")

    def test_wrong_process_or_stage_is_blocked(self):
        self.publish()
        with self.assertRaisesRegex(manifest.ManifestError, "identity/fingerprint"):
            self.verify(stage="MINT0")

    def test_extra_expected_output_is_blocked(self):
        self.publish()
        with self.assertRaisesRegex(manifest.ManifestError, "output entries"):
            self.verify(required_output=["res_1.dat", "res_2.dat"])

    def test_path_escape_is_blocked(self):
        with self.assertRaisesRegex(manifest.ManifestError, "Traversal"):
            self.publish(required_output=["../outside.dat"])

    def test_symlink_output_is_blocked(self):
        link = self.work / "linked.dat"
        link.symlink_to(self.work / self.filename)
        with self.assertRaisesRegex(manifest.ManifestError, "Missing/linked"):
            self.publish(required_output=["linked.dat"])

    def test_missing_output_is_blocked(self):
        with self.assertRaisesRegex(manifest.ManifestError, "Missing/linked"):
            self.publish(required_output=["missing.dat"])

    def test_duplicate_expected_output_is_blocked(self):
        with self.assertRaisesRegex(manifest.ManifestError, "Duplicate output names"):
            self.publish(required_output=["res_1.dat", "res_1.dat"])

    def test_corrupt_json_is_blocked(self):
        published = self.publish()
        published.write_text("{invalid json")
        with self.assertRaisesRegex(manifest.ManifestError, "Invalid completion JSON"):
            self.verify()

    def test_forged_manifest_extra_field_is_blocked(self):
        published = self.publish()
        content = json.loads(published.read_text())
        content["unauthorized"] = True
        published.write_text(json.dumps(content))
        with self.assertRaisesRegex(manifest.ManifestError, "Unexpected completion schema"):
            self.verify()


if __name__ == "__main__":
    unittest.main()
