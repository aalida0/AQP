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

    def test_submission_from_clean_staging_root_only(self):
        """Use mocked clients to verify JO packaging without a real PanDA task."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jo_dir = root / "jo"
            jo_dir.mkdir()
            jo = jo_dir / "mc.aMCPy8EG_Zee_delta111.py"
            jo.write_text("gridpack_compile=RECOMPILE_GRIDPACK\n")
            gridpack = root / "mc_13TeV.test.GRID.tar.gz"
            gridpack.write_bytes(b"synthetic test file")
            stage_parent = root / "stage"
            mock_bin = root / "mock_bin"
            mock_bin.mkdir()
            rucio = mock_bin / "rucio"
            rucio.write_text(
                '#!/bin/bash\n'
                'if [[ "$1" == list-files ]]; then\n'
                '  echo "user.aalida:mc_13TeV.test.GRID.tar.gz"\n'
                '  echo "Total files : 1"\n'
                '  exit 0\n'
                'fi\n'
                'exit 1\n'
            )
            proxy = mock_bin / "voms-proxy-info"
            proxy.write_text("#!/bin/bash\nexit 0\n")
            pathena = mock_bin / "pathena"
            pathena.write_text(
                "#!/bin/bash\n"
                'echo "MOCK_PANDA_STAGE=$PWD"\n'
                "echo \"MOCK_PANDA_JO_LIST=$(find . -maxdepth 1 -name 'mc*.py' -type f)\"\n"
                'printf "MOCK_PANDA_ARGS=%s\\n" "$*"\n'
            )
            for binary in (rucio, proxy, pathena):
                binary.chmod(0o755)
            env = dict(
                os.environ,
                AQP_REPO=str(REPO),
                AQP_RUCIO_USER="aalida",
                AQP_JO_DIR=str(jo_dir),
                AQP_GRID_STAGE_DIR=str(stage_parent),
                AQP_OUTPUT_TAG="norecompile_v3",
                PATH=str(mock_bin) + os.pathsep + os.environ.get("PATH", ""),
            )
            p = subprocess.run(
                [
                    "bash", str(SCRIPT), "submit", "delta111",
                    str(gridpack), "delta111_norecompile_gridfix_v3",
                ],
                env=env,
                input="SUBMIT\n",
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(p.returncode, 0, p.stderr + p.stdout)
            self.assertIn("RUCIO_ONE_FILE_VERIFIED=", p.stdout)
            self.assertIn("MOCK_PANDA_JO_LIST=./mc.aMCPy8EG_Zee_delta111.py", p.stdout)
            self.assertIn("GRIDPACK_RECOMPILE=0 Gen_tf.py", p.stdout)
            self.assertIn("--jobConfig=./", p.stdout)
            self.assertIn("OUT_DS=user.aalida.AQP.Zee2jet.PR426.delta111.EVNT20.norecompile_v3", p.stdout)
            self.assertIn("IN_DID=user.aalida:user.aalida.AQP.Zee2jet.PR426.delta111.GRID.delta111_norecompile_gridfix_v3", p.stdout)
            stages = list(stage_parent.iterdir())
            self.assertEqual(len(stages), 1)
            self.assertEqual([f.name for f in stages[0].iterdir()], [jo.name])


if __name__ == "__main__":
    unittest.main()
