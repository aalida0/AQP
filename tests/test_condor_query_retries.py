"""Offline tests for the Condor retry installer and its generated function."""
from __future__ import annotations

import ast
import importlib.util
import hashlib
import tempfile
from pathlib import Path
import subprocess
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install_condor_query_retries.py"
spec = importlib.util.spec_from_file_location("aqp_query_installer", SCRIPT)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class QueryError(Exception):
    pass


class QueryPatchTests(unittest.TestCase):
    def query(self):
        f = ast.parse(installer.REPLACEMENT).body[0]
        ns = {"subprocess": subprocess, "ClusterManagmentError": QueryError}
        exec(compile(ast.Module(body=[f], type_ignores=[]), "<query>", "exec"), ns)
        return ns["_aqp_query"]

    def test_one_transient_failure_then_success(self):
        bad = subprocess.CompletedProcess([], 1, "", "Failed to receive remote ad.")
        good = subprocess.CompletedProcess([], 0, "4172040 0 4\n", "")
        with mock.patch("subprocess.run", side_effect=[bad, good]) as run, \
             mock.patch("time.sleep") as sleep:
            result = self.query()(["condor_q", "4172040"])
        self.assertEqual(result, [["4172040", "0", "4"]])
        self.assertEqual(run.call_count, 2)
        sleep.assert_called_once_with(1)

    def test_success_with_stderr_warning(self):
        good = subprocess.CompletedProcess([], 0, "4172040 0 4\n", "Warning: collector late")
        with mock.patch("subprocess.run", return_value=good) as run:
            result = self.query()(["condor_q", "4172040"])
        self.assertEqual(result, [["4172040", "0", "4"]])
        run.assert_called_once()

    def test_permanent_failure_does_not_retry(self):
        bad = subprocess.CompletedProcess([], 1, "", "Invalid constraint expression")
        with mock.patch("subprocess.run", return_value=bad) as run, \
             mock.patch("time.sleep") as sleep:
            with self.assertRaisesRegex(QueryError, "Invalid constraint"):
                self.query()(["condor_q", "bogus"])
        run.assert_called_once()
        sleep.assert_not_called()

    def test_five_persistent_transient_failures_remain_fatal(self):
        bad = subprocess.CompletedProcess([], 1, "", "Failed to receive remote ad.")
        with mock.patch("subprocess.run", return_value=bad) as run, \
             mock.patch("time.sleep") as sleep:
            with self.assertRaisesRegex(QueryError, "Failed to receive remote ad"):
                self.query()(["condor_q", "4172040"])
        self.assertEqual(run.call_count, 5)
        self.assertEqual([x.args[0] for x in sleep.call_args_list], [1, 2, 4, 8])

    def test_timeout_recovered(self):
        exc = subprocess.TimeoutExpired(["condor_q"], 45)
        good = subprocess.CompletedProcess([], 0, "", "")
        with mock.patch("subprocess.run", side_effect=[exc, good]) as run, \
             mock.patch("time.sleep") as sleep:
            self.assertEqual(self.query()(["condor_q"]), [])
        self.assertEqual(run.call_count, 2)
        sleep.assert_called_once()

    def test_patch_preserves_states_function(self):
        old = (
            "def _aqp_query(args):\n"
            "    try:\n"
            "        result = subprocess.run(args, capture_output=True, text=True, timeout=45)\n"
            "    except (OSError, subprocess.TimeoutExpired) as exc:\n"
            "        raise ClusterManagmentError('Condor query failed: %s' % exc)\n"
            "    if result.returncode != 0 or result.stderr.strip():\n"
            "        raise ClusterManagmentError('Condor query error: %s %s' %\n"
            "                                   (result.returncode, result.stderr.strip()))\n"
            "    return [line.split() for line in result.stdout.splitlines() if line.strip()]\n"
            "\n\n"
            "def _aqp_states(ids):\n"
            "    return {'safe': True}\n"
        )
        updated = installer.patch_source(old)
        self.assertIn("AQP_CONDOR_QUERY_RETRY_V4", updated)
        self.assertIn("def _aqp_states(ids):\n    return {'safe': True}", updated)
        self.assertEqual(len(ast.parse(updated).body), 2)
        with self.assertRaisesRegex(ValueError, "already present"):
            installer.patch_source(updated)

    def test_isolated_install_leaves_original_backend_and_launcher_unchanged(self):
        source = (
            "import subprocess\n"
            "def _aqp_query(args):\n"
            "    try:\n"
            "        result = subprocess.run(args, capture_output=True, text=True, timeout=45)\n"
            "    except (OSError, subprocess.TimeoutExpired) as exc:\n"
            "        raise ClusterManagmentError('Condor query failed: %s' % exc)\n"
            "    if result.returncode != 0 or result.stderr.strip():\n"
            "        raise ClusterManagmentError('Condor query error: %s %s' %\n"
            "                                   (result.returncode, result.stderr.strip()))\n"
            "    return [line.split() for line in result.stdout.splitlines() if line.strip()]\n"
            "\n\n"
            "def _aqp_states(ids):\n"
            "    return {}\n"
        )
        sha = hashlib.sha256(source.encode()).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            original_dir = repo / ".condor"
            scripts = repo / "scripts"
            (original_dir / "bootstrap_v3").mkdir(parents=True)
            scripts.mkdir()
            (original_dir / "bootstrap_v3/sitecustomize.py").write_text("# original\n")
            candidate = original_dir / "cluster.py"
            candidate.write_text(source)
            launcher = scripts / "gridpack.sh"
            old_launcher = (
                '#!/usr/bin/env bash\n'
                'repo=$(pwd)\n'
                'patchroot="${GP_PATCH_ROOT:-$repo/.condor}"\n'
                'candidate="$patchroot/cluster.py"\n'
                'PIN=' + sha + '\n'
            )
            launcher.write_text(old_launcher)
            with mock.patch.object(installer, "ORIGINAL_SHA", sha):
                prepared = installer.prepare(repo)
                installer.install_staged(prepared)
            self.assertEqual(candidate.read_text(), source)
            self.assertEqual(launcher.read_text(), old_launcher)
            self.assertEqual(
                hashlib.sha256((original_dir / "retry_v4/cluster.py").read_bytes()).hexdigest(),
                prepared[-1],
            )
            staged = (scripts / "gridpack_retry_v4.sh").read_text()
            self.assertIn(".condor/retry_v4", staged)
            self.assertIn(prepared[-1], staged)
            self.assertIn("AQP_CONDOR_QUERY_RETRY_V4",
                          (original_dir / "retry_v4/cluster.py").read_text())


if __name__ == "__main__":
    unittest.main()
