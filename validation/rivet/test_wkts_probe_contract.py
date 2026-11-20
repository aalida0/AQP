"""Static regression guard for the isolated AQP kT splitting probe."""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent

class WKTSContractTests(unittest.TestCase):
    def test_physics_selection_and_met_projection(self):
        c = (ROOT / "AQP_WKTSPLITTINGS.cc").read_text()
        self.assertIn('declare("AQP_W_MET", MissingMomentum());', c)
        self.assertIn('apply<MissingMomentum>(event, "AQP_W_MET")', c)
        self.assertIn("missing.pT() < 25 * GeV", c)
        self.assertIn("80.4 * GeV, 60 * GeV, 100 * GeV", c)
        self.assertIn('declare("Jets", jets);', c)
        self.assertIn("MC_KTSPLITTINGS_BASE::analyze(event);", c)
        self.assertIn("RIVET_DECLARE_PLUGIN(AQP_WKTSPLITTINGS)", c)

    def test_minimal_metkey_probe(self):
        source = (ROOT / "AQP_WKTSPLITTINGS_METKEY.cc").read_text()
        worker = (ROOT / "aqp_wkts_metkey_probe.sh").read_text()
        submit = (ROOT / "aqp_wkts_metkey_probe.sub").read_text()
        jo = (ROOT / "aqp_wkts_smoke_evnt.py").read_text()
        self.assertIn('declare(MissingMomentum(), "AQP_W_MET")', source)
        self.assertIn('apply<MissingMom>(event, "AQP_W_MET")', source)
        self.assertIn('declare(lf, "Leptons")', source)
        self.assertIn("AQP_WKTSPLITTINGS_METKEY", jo)
        self.assertIn("should_transfer_files = YES", submit)
        self.assertIn("condor_logs/", submit)
        self.assertNotIn("FileSystemDomain =", submit)
        self.assertLess(worker.index("asetup AthGeneration,23.6.63"),
                        worker.index('AQP_WKTS_SOURCE_DIR="/home/aalida/'))
        self.assertIn("METKEY_OUTPUT_EXISTS", worker)
        self.assertIn("AQP_WKTS_METKEY_PASS=", worker)
        for setting in ("set -e", "set -u", "pipefail"):
            self.assertNotIn(setting+"\\n", worker)

    def test_condor_contract(self):
        submit = (ROOT / "aqp_wkts_smoke.sub").read_text()
        worker = (ROOT / "aqp_wkts_smoke.sh").read_text()
        self.assertNotIn("FileSystemDomain = ", submit)
        self.assertIn("should_transfer_files = YES", submit)
        self.assertIn("when_to_transfer_output = ON_EXIT", submit)
        self.assertIn('transfer_output_files = ""', submit)
        self.assertIn("condor_logs/", submit)
        for setting in ("set -e", "set -u", "pipefail"):
            self.assertNotIn(setting+"\n", worker)
        self.assertIn('AQP_WKTS_SMOKE_PASS=', worker)
        self.assertIn('OUTPUT_ALREADY_EXISTS', worker)
        self.assertIn("rivet-build", worker)
        self.assertIn('AQP_WKTS_SOURCE_DIR="/home/aalida/AQP/validation/rivet"', worker)
        self.assertNotIn('BASE="/home/aalida', worker)
        self.assertNotIn('$BASE/', worker)
        self.assertLess(worker.index("asetup AthGeneration,23.6.63"),
                        worker.index('AQP_WKTS_SOURCE_DIR="/home/aalida/'))
        self.assertIn('athena.py "$AQP_WKTS_SOURCE_DIR/aqp_wkts_smoke_evnt.py"', worker)
        self.assertIn("ATHENA_JOBOPTIONS_MISSING", worker)
        self.assertIn("AQP_WKTS_OFFICIAL_ISOLATED_PASS=", worker)
        self.assertLess(worker.index("AQP_WKTS_CONTROL=official"),
                        worker.index('rivet-build "$PLUGINS'))

if __name__ == "__main__":
    unittest.main()
