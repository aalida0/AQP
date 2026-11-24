import tempfile
import unittest
from pathlib import Path
from aqp_rivet_stage_missing_xrootd import replicas, adler

NAME = "user.aalida.53564233._000291.EVNT.pool.root"
ROW = f"| user.aalida | {NAME} | 193.156 MB | f381637e | MWT2_UC_SCRATCHDISK: root://fax.mwt2.org:1094//atlasscratchdisk/{NAME} |"
DAVS = f"| user.aalida | {NAME} | 193.156 MB | f381637e | UAM-LCG2_SCRATCHDISK: davs://griddc03.ft.uam.es:8446/{NAME} |"

class TestStaging(unittest.TestCase):
    def test_catalogue(self):
        checksum, urls = replicas(ROW+"\n"+DAVS, NAME)
        self.assertEqual(checksum, "f381637e")
        self.assertEqual(urls, ["root://fax.mwt2.org:1094//atlasscratchdisk/"+NAME])
        with self.assertRaises(ValueError):
            replicas(DAVS, NAME)
        with self.assertRaises(ValueError):
            replicas(ROW+"\n"+DAVS.replace("f381637e", "deadbeef"), NAME)
    def test_adler(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/"file"
            p.write_bytes(b"Wikipedia")
            self.assertEqual(adler(p), "11e60398")

if __name__ == "__main__":
    unittest.main()
