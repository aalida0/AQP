#!/usr/bin/env python3
"""Offline tests for preserving Wenu's process-local Condor timing changes."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch as mock_patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "aqp_prepare_bundled_condor_patch.py"
spec = importlib.util.spec_from_file_location("aqp_prepare_bundled_condor_patch", SCRIPT)
import sys
sys.path.insert(0, str(SCRIPT.parent))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

CENTRAL_FIXTURE = """class CondorCluster:
    def submit(self, prog, argument, cwd, log=None):
        if log is None:
            log = '/dev/null'
        return log

    def submit2(self, prog, argument, cwd, log=None):
        if log is None:
            log = '/dev/null'
        return log

    def control(self, me_dir):
        return None
"""


class BundledPatchTests(unittest.TestCase):
    def test_timing_instrumentation_is_exact_and_twice(self):
        for cfg in module.BUNDLES:
            with self.subTest(configuration=cfg):
                bundled = module.add_known_timing(CENTRAL_FIXTURE, cfg)
                self.assertEqual(bundled.count(module.timing_replacement(cfg)), 2)
                self.assertEqual(bundled.count("def control(self"), 1)
                compile(bundled, cfg + "/cluster.py", "exec")

    def test_original_blank_line_after_step_assignment_is_preserved(self):
        for cfg in module.BUNDLES:
            with self.subTest(configuration=cfg):
                bundled = module.add_known_timing(CENTRAL_FIXTURE, cfg)
                self.assertIn(
                    "step = str(argument[3]) if len(argument) > 3 else 'unknown'\n\n"
                    "                if step in ('0', '1'):",
                    bundled,
                )
                unexpected = bundled.replace(
                    "step = str(argument[3]) if len(argument) > 3 else 'unknown'\n\n",
                    "step = str(argument[3]) if len(argument) > 3 else 'unknown'\n",
                    1,
                )
                with self.assertRaises(ValueError):
                    module.build(CENTRAL_FIXTURE, unexpected, cfg)

    def test_delta441_legacy_log_path_is_preserved_not_silently_changed(self):
        bundled = module.add_known_timing(CENTRAL_FIXTURE, "delta441_backup")
        self.assertIn("/WENU/delta441/aqp_condor_timing", bundled)
        self.assertNotIn("/WENU/delta441_backup/aqp_condor_timing", bundled)

    def test_unexpected_source_change_fails_closed(self):
        bundled = module.add_known_timing(CENTRAL_FIXTURE, "standard111")
        modified = bundled.replace("return log", "return None", 1)
        with self.assertRaisesRegex(ValueError, "beyond approved timing instrumentation"):
            module.build(CENTRAL_FIXTURE, modified, "standard111")

    def test_timing_survives_both_fix_stages(self):
        cfg = "delta221"
        bundled = module.add_known_timing(CENTRAL_FIXTURE, cfg)
        with (mock_patch.object(module, "patch_status",
                                side_effect=lambda txt: txt + "\n# status-fix\n"),
              mock_patch.object(module, "patch_submit",
                                side_effect=lambda txt: txt + "\n# submit-fix\n")):
            candidate = module.build(CENTRAL_FIXTURE, bundled, cfg)
        self.assertEqual(candidate.count(module.timing_replacement(cfg)), 2)
        self.assertIn("# status-fix", candidate)
        self.assertIn("# submit-fix", candidate)

    def test_expected_input_hashes_are_distinct(self):
        self.assertEqual(len({item[0] for item in module.BUNDLES.values()}), 4)

    def test_original_timing_block_must_be_present_once_per_method(self):
        bad = CENTRAL_FIXTURE.replace("log = '/dev/null'", "log = None", 1)
        with self.assertRaises(ValueError):
            module.add_known_timing(bad, "standard111")


if __name__ == "__main__":
    unittest.main()
