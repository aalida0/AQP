import tempfile
import unittest
from pathlib import Path

from aqp_rivet_fresh_pilot import ROUTINES, PLAN, choose_pair


class FreshRivetPilotTests(unittest.TestCase):
    def test_routines_and_correct_versions(self):
        self.assertEqual(len(PLAN), 8)
        self.assertIn(("Wenu", "standard111", "v1"), PLAN)
        self.assertNotIn(("Wenu", "standard111", "v2"), PLAN)
        for routines in ROUTINES.values():
            self.assertIn("MC_WEIGHTS", routines)
            self.assertIn("MC_XS", routines)
        self.assertNotIn("CMS_2017_I1610623", ROUTINES["Wenu"])

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
