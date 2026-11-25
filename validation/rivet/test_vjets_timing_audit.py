import io
import tarfile
import tempfile
import unittest
from pathlib import Path

from aqp_vjets_timing_audit import measured_timing, summarize, timing_fields


class TimingAuditTests(unittest.TestCase):
    def test_archive_worker_timing(self):
        payload = (b"gen_wall_seconds=125\ngen_wall_seconds_gnu=124.5\n"
                   b"gen_user_cpu_seconds=100\ngen_system_cpu_seconds=4.5\n"
                   b"gen_exit_code=0\n")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"job.log.generate"
            with tarfile.open(path, "w:gz") as tf:
                member = tarfile.TarInfo("job/generation_timing.txt")
                member.size = len(payload)
                tf.addfile(member, io.BytesIO(payload))
            wall, cpu, source = measured_timing(path, "")
            self.assertEqual((wall, cpu), (124.5, 104.5))
            self.assertIn("generation_timing.txt", source)

    def test_missing_and_conflicting(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"log"
            path.write_text("no timing")
            self.assertEqual(measured_timing(path, ""), (None, None, ""))
        with self.assertRaises(ValueError):
            timing_fields("gen_wall_seconds=1\ngen_wall_seconds=2")

    def test_cost_uses_only_paired_weight_moments(self):
        rows = [dict(entries=5, sumW=4, sumW2=8, cpu_s=20),
                dict(entries=5, sumW=100, sumW2=2000, cpu_s=None)]
        self.assertEqual(summarize(rows, "cpu_s"), (1, 5, 20, 4, 10))


if __name__ == "__main__":
    unittest.main()
