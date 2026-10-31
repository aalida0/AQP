#!/usr/bin/env python3
"""Regression for attributed LHE <event ...> tags in saved FxFx checkpoints."""
import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest

SCRIPT=Path(__file__).resolve().parents[1]/"scripts/check_wenu_fxfx_pr426_saved_grids.py"
spec=importlib.util.spec_from_file_location("aqp_saved_grid_inspect",SCRIPT)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class LheEventTags(unittest.TestCase):
    def _fixture(self, base, opening, num=200):
        work=Path(base)
        process=work/"PROCNLO_loop_sm-no_b_mass_0"
        sub=process/"SubProcesses"
        (sub/"P0_fake/GF1").mkdir(parents=True)
        (sub/"P0_fake/GF1/mint_grids").write_text("stub\n")
        (sub/"job_status.pkl").write_bytes(b"stub")
        (sub/"cuts.f").write_text(
            "      logical function passcuts_fxfx(p,pQCD,nQCD)\n"
            "c original inclusive FxFx\n"
            "      logical function passcuts_jets(p,pQCD,nQCD)\n"
        )
        (process/"Cards").mkdir()
        (process/"Cards/run_card.dat").write_text(
            "3 = ickkw\nFalse = mcatnlo_delta\n"
            "1, 1, 1 = folding\n325100 = lhaid\nbias = event_norm\n"
        )
        events=process/"Events/run_01"
        events.mkdir(parents=True)
        with (events/"events.lhe").open("w") as stream:
            stream.write('<LesHouchesEvents version="3.0">\n')
            for i in range(num):
                stream.write(f'{opening.format(i=i)}\n')
                stream.write(" 1 1 1.0 1 1 1\n</event>\n")
            stream.write("</LesHouchesEvents>\n")
        return work

    def test_attributed_event_openers_pass(self):
        for opener in ("<event id='{i}'>", '<event id="{i}" npLO="1">',
                       "<event>"):
            with self.subTest(opener=opener), tempfile.TemporaryDirectory() as tmp:
                work=self._fixture(tmp,opener)
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    mod.inspect("before",work)
                self.assertIn("SAVED_GRIDS_PREFLIGHT_PASS",output.getvalue())

    def test_missing_event_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=self._fixture(tmp,"<event id='{i}'>",num=199)
            with self.assertRaisesRegex(ValueError,"incomplete"):
                mod.inspect("before",work)

    def test_unrelated_eventgroup_not_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=self._fixture(tmp,"<eventgroup id='{i}'>")
            with self.assertRaisesRegex(ValueError,"incomplete"):
                mod.inspect("before",work)

if __name__=="__main__":
    unittest.main()
