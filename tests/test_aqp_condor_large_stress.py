#!/usr/bin/env python3
"""Regression tests for the source pins used by the large Condor stress run.

No HTCondor/MadGraph commands, source modifications, or event generation.
"""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import aqp_condor_large_stress as stress


class LargeCondorStressPinTests(unittest.TestCase):
    def test_all_four_candidate_hashes_are_complete(self):
        stress.validate_candidate_fingerprints()
        self.assertEqual(set(stress.EXPECTED_CANDIDATES), set(stress.BUNDLES))
        self.assertTrue(all(len(digest) == 64
                            for digest in stress.EXPECTED_CANDIDATES.values()))

    def test_delta111_exact_verified_hash(self):
        # Regression: originally mistyped 60-character pin stopped the campaign
        # after a successful standard111 run.
        self.assertEqual(
            stress.EXPECTED_CANDIDATES["delta111"],
            "b2879ef87fa4f1a4f70a79699b2db6c1025c0770c3828d704a6c19acb5d2d17a",
        )

    def test_truncated_hash_fails_at_startup(self):
        bad = dict(stress.EXPECTED_CANDIDATES)
        bad["delta111"] = bad["delta111"][:60]
        with patch.object(stress, "EXPECTED_CANDIDATES", bad):
            with self.assertRaisesRegex(ValueError, "Malformed expected SHA256"):
                stress.validate_candidate_fingerprints()

    def test_missing_configuration_fails_at_startup(self):
        bad = dict(stress.EXPECTED_CANDIDATES)
        del bad["delta221"]
        with patch.object(stress, "EXPECTED_CANDIDATES", bad):
            with self.assertRaisesRegex(ValueError, "fingerprint set differs"):
                stress.validate_candidate_fingerprints()

    def test_invalid_hex_hash_fails_at_startup(self):
        bad = dict(stress.EXPECTED_CANDIDATES)
        bad["standard111"] = "g" * 64
        with patch.object(stress, "EXPECTED_CANDIDATES", bad):
            with self.assertRaisesRegex(ValueError, "Malformed expected SHA256"):
                stress.validate_candidate_fingerprints()


if __name__ == "__main__":
    unittest.main()
