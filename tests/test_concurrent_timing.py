#!/usr/bin/env python3
"""Offline regression: separate concurrently submitted HTCondor histories."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from runtime import gridpack_timing as timing
from check_concurrent_gridpacks import check


class IndependentRuns(unittest.TestCase):
    def test_condor_query_is_scoped_to_one_run(self):
        with TemporaryDirectory() as td:
            a = Path(td) / "run.A"; b = Path(td) / "run.Along"
            a.mkdir(); b.mkdir()
            rows = [
                dict(ClusterId=121, ProcId=0, Iwd=str(a / "SubProcesses" / "P0"),
                     Cmd=str(a / "SubProcesses" / "P0" / "ajob1"), Args="1.0 F 0 0",
                     QDate=1500, JobStatus=4, ExitCode=0, NumJobStarts=1,
                     CumulativeRemoteUserCpu=20, CumulativeRemoteSysCpu=2),
                dict(ClusterId=122, ProcId=0, Iwd=str(b / "SubProcesses" / "P0"),
                     Cmd=str(b / "SubProcesses" / "P0" / "ajob1"), Args="1.0 F 0 1",
                     QDate=1500, JobStatus=4, ExitCode=0, NumJobStarts=1,
                     CumulativeRemoteUserCpu=10, CumulativeRemoteSysCpu=3),
            ]
            def query(args, **_):
                expr = args[args.index("-constraint") + 1]
                self.assertIn("regexp(", expr)
                self.assertIn(str(a) + os.sep, expr)
                self.assertIn("Iwd", expr)
                self.assertIn("Cmd", expr)
                self.assertIn("-json", args)
                # Return both to exercise the independent post-query safety filter.
                return SimpleNamespace(stdout=json.dumps(rows), returncode=0)
            with patch.object(timing.subprocess, "run", side_effect=query):
                jobs, err, candidates = timing.history(a, 1100, 1800, [])
            self.assertIsNone(err)
            self.assertEqual(candidates, 2)
            self.assertEqual([j["job_id"] for j in jobs], ["121.0"])
            self.assertEqual(jobs[0]["stage"], "grid")
            self.assertEqual(jobs[0]["cpu_seconds"], 22)

    def test_concurrent_reports_reject_shared_job(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            reports = []
            for run, worker in (("a", "121.0"), ("b", "121.0")):
                folder = root / run
                folder.mkdir()
                (folder / "mc_test.GRID.tar.gz").write_bytes(b"test")
                data = dict(run=run, transform_exit=0, result_exit=0,
                            worker_accounting_complete=True,
                            worker_job_ids=[worker], history_worker_count=1,
                            start_epoch=1000, end_epoch=1200,
                            remote_cpu_seconds=1,
                            stages=[dict(history_workers=1, accounting_complete=True)])
                report = folder / "timing_summary.json"
                report.write_text(json.dumps(data))
                reports.append(report)
            with self.assertRaisesRegex(AssertionError, "Worker IDs counted in both"):
                check(*reports)


if __name__ == "__main__":
    unittest.main()
