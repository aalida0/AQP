import tempfile
import unittest
from pathlib import Path

from aqp_rivet_fresh_pilot import ROUTINES, PLAN, TASKS, production_did, choose_pair


class FreshRivetPilotTests(unittest.TestCase):
    def test_routines_and_correct_versions(self):
        self.assertEqual(len(PLAN), 8)
        self.assertIn(("Wenu", "standard111", "v1"), PLAN)
        self.assertNotIn(("Wenu", "standard111", "v2"), PLAN)
        for routines in ROUTINES.values():
            self.assertIn("MC_WEIGHTS", routines)
            self.assertIn("MC_XS", routines)
        self.assertNotIn("CMS_2017_I1610623", ROUTINES["Wenu"])

    def test_exact_production_dids(self):
        self.assertEqual(set(TASKS), set(PLAN))
        self.assertEqual(TASKS[("Wenu", "standard111", "v1")], "53692983")
        self.assertEqual(production_did("Wenu", "standard111", "v1"),
            "user.aalida:user.aalida.AQP.Wenu.standard111.seed817263.FxFx2M.v1_EVNT.pool.root")
        self.assertEqual(production_did("Zee", "delta441", "v3"),
            "user.aalida:user.aalida.AQP.Zee.delta441.FxFx2M.v3_EVNT.pool.root")
        with self.assertRaises(ValueError):
            production_did("Wenu", "standard111", "v2")

    def test_select_matching_job_not_first_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"user.aalida.123._000002.log.generate"
            path.write_text("Using FxFx cross section recipe: xs = 2 / 1000000\nMetaData: cross-section (nb)= 2\n")
            entries = [("user.aalida.123._000001.EVNT.pool.root", 5000),
                       ("user.aalida.123._000002.EVNT.pool.root", 5000)]
            name, n, log, info = choose_pair(entries, [path])
            self.assertEqual(name, entries[1][0])
            self.assertEqual(n, 5000)
            self.assertEqual(info["xs_pb"], 2000)
            with self.assertRaises(ValueError):
                choose_pair(entries[:1], [path])


if __name__ == "__main__":
    unittest.main()
