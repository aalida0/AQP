#!/usr/bin/env python3
"""Offline contract checks for isolated Wenu Condor v2 bootstrap pinning."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import build_wenu_condor_bootstrap_v2 as builder


class TestBootstrap(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.source = root / "original_bootstrap"
        self.source.mkdir()
        self.original = self.source / "sitecustomize.py"
        self.original.write_text(
            "EXPECTED_SHA = '" + builder.PINNED_V1 + "'\n"
            "def check(actual):\n"
            "    return actual == EXPECTED_SHA\n",
            encoding="utf-8",
        )
        self.candidate = root / "cluster.py"
        self.candidate.write_text("def _aqp_states(ids): return {}\n")
        self.target = root / "private_bootstrap"

    def test_creates_pinned_copy_without_mutating_source(self):
        orig_text = self.original.read_text()
        with patch.object(builder, "sha256", return_value=builder.PINNED_V2):
            builder.make_bootstrap(self.source, self.candidate, self.target)
        self.assertEqual(self.original.read_text(), orig_text)
        amended = (self.target / "sitecustomize.py").read_text()
        self.assertEqual(amended, orig_text.replace(
            builder.PINNED_V1, builder.PINNED_V2, 1))

    def test_mismatched_candidate_rejected(self):
        with self.assertRaisesRegex(ValueError, "candidate SHA256 mismatch"):
            builder.make_bootstrap(self.source, self.candidate, self.target)
        self.assertFalse(self.target.exists())

    def test_original_without_unique_pin_rejected(self):
        self.original.write_text("EXPECTED_SHA = 'other'\n")
        with patch.object(builder, "sha256", return_value=builder.PINNED_V2):
            with self.assertRaisesRegex(ValueError, "exactly one"):
                builder.make_bootstrap(self.source, self.candidate, self.target)

    def test_refuses_overwrite(self):
        self.target.mkdir()
        with patch.object(builder, "sha256", return_value=builder.PINNED_V2):
            with self.assertRaisesRegex(ValueError, "overwrite"):
                builder.make_bootstrap(self.source, self.candidate, self.target)


if __name__ == "__main__":
    unittest.main(verbosity=2)
