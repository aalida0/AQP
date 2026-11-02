"""Regression for Rucio LFN / Gen_tf.py 13 TeV gridpack naming.

Purely local: tests the script's read-only plan mode, without Rucio,
PanDA, grid credentials or actual archive integration.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "aqp_zee_grid_rucio.sh"


class TestZeeGridRucioPlan(unittest.TestCase):
    def invoke(self, filename, tag="delta111_test_20261102_v2"):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / filename
            path.write_bytes(b"synthetic stand-in, not a gridpack")
            env = dict(
                os.environ,
                AQP_REPO=str(REPO),
                AQP_RUCIO_USER="aalida",
                AQP_RSE="CERN-PROD_SCRATCHDISK",
            )
            return subprocess.run(
                ["bash", str(SCRIPT), "plan", "delta111", str(path), tag],
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

    def test_valid_gridpack_lfn_preserved_for_gentf(self):
        name = "mc_13TeV.aMCPy8EG_Zee_FxFx_2jets_DRjj_PR426_delta111.MG3511.GRID.tar.gz"
        completed = self.invoke(name)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("GRIDPACK_LFN=user.aalida:" + name, completed.stdout)
        self.assertIn("--inputGeneratorFile=%IN", completed.stdout)
        self.assertIn("GRIDPACK_RECOMPILE=1", completed.stdout)
        self.assertIn("RSE=CERN-PROD_SCRATCHDISK", completed.stdout)
        self.assertIn("delta111_test_20261102_v2", completed.stdout)

    def test_renamed_gridpack_rejected_before_upload(self):
        completed = self.invoke(
            "AQP.Zee2jet.delta111.delta111_test_20261102.abcd1234.GRID.tar.gz"
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Invalid ATLAS 13 TeV gridpack filename", completed.stderr)

    def test_wrong_energy_filename_rejected(self):
        completed = self.invoke("mc_13p6TeV.Zee.GRID.tar.gz")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("mc_13TeV", completed.stderr)


if __name__ == "__main__":
    unittest.main()
