#!/usr/bin/env python3
"""Offline tests for fail-closed upstream PR #426 FxFx passcuts patcher."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/aqp_prepare_fxfx_exclusive_kt_patch.py"
spec = importlib.util.spec_from_file_location("aqp_fxfx_exclusive_kt", SCRIPT)
import sys
sys.modules[spec.name] = module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

ORIGINAL = (
    "c BEFORE untouched\n"
    + module.START + "\n"
    + "c In case of FxFx merging\n"
    + module.OLD_DECL
    + "      passcuts_fxfx=.true.\n"
    + module.OLD_SELECT
    + "c Second apply the actual ptj cut\n"
    + "      if (minval(FxFx_ren_scales(0:nFxFx_ren_scales)).lt.ptj) then\n"
    + "         passcuts_fxfx=.false.\n"
    + "         return\n"
    + "      endif\n"
    + "      return\n"
    + "      end\n\n"
    + module.NEXT + "p,pQCD,nQCD,pgamma,nph,is_nph_iso,ickkw)\n"
    + "c AFTER untouched\n"
)


class Pr426FxfxTests(unittest.TestCase):
    def test_exact_patch_changes_only_fxfx(self):
        out = module.patched_text(ORIGINAL)
        self.assertNotEqual(out, ORIGINAL)
        self.assertIn(module.NEW_DECL, out)
        self.assertIn(module.NEW_SELECT, out)
        self.assertNotIn(module.OLD_SELECT, out)
        self.assertTrue(out.startswith("c BEFORE untouched\n"))
        self.assertTrue(out.endswith("c AFTER untouched\n"))
        self.assertIn("c Second apply the actual ptj cut", out)

    def test_patching_twice_fails(self):
        out = module.patched_text(ORIGINAL)
        with self.assertRaisesRegex(ValueError, "Unexpected original"):
            module.patched_text(out)

    def test_unknown_variant_fails_closed(self):
        modified = ORIGINAL.replace(
            "amcatnlo_fastjetppgenkt_etamax_timed",
            "some_other_jet_algorithm",
            1,
        )
        with self.assertRaisesRegex(ValueError, "Unexpected original"):
            module.patched_text(modified)

    def test_missing_or_duplicate_function_fails_closed(self):
        for src in (ORIGINAL.replace(module.START, "other function"),
                    ORIGINAL + ORIGINAL):
            with self.subTest(source=src[-20:]):
                with self.assertRaisesRegex(ValueError, "boundaries"):
                    module.patched_text(src)

    def test_patch_matches_upstream_method(self):
        out = module.patched_text(ORIGINAL)
        self.assertIn("amcatnlo_fastjetdmergemax(nQCD-2).lt.ptj**2", out)
        self.assertIn("sycut=0d0", out)
        self.assertIn("if (nQCD.gt.1 .and. ptj.gt.0d0) then", out)
        self.assertIn("external amcatnlo_fastjetdmergemax", out)

    def test_file_encoding_is_plain_text(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "cuts.f"
            target.write_text(ORIGINAL, encoding="utf-8")
            after = module.patched_text(target.read_text(encoding="utf-8"))
            self.assertIn(module.NEW_SELECT, after)


if __name__ == "__main__":
    unittest.main()
