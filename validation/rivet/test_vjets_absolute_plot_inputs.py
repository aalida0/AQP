"""Verify path-only transformations and reject ambiguous canonical paths."""
import gzip
import tempfile
import unittest
from pathlib import Path

from aqp_vjets_absolute_plot_inputs import common_blocks


class TestPlotInputs(unittest.TestCase):
    def test_alias_preserves_payload_and_excludes_raw(self):
        alias = "/MC_ZJETS:LMODE=EL/jet_HT"
        bare = "/MC_ZJETS/jet_HT"
        block = ("BEGIN YODA_HISTO1D_V2 " + alias + "\n"
                 "Path: " + alias + "\n"
                 "Title: keep original title\n"
                 "---\n1 2 3.141592653589 9.87654321\n"
                 "END YODA_HISTO1D_V2\n")
        raw = block.replace(alias, "/RAW" + alias)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.yoda.gz"
            with gzip.open(source, "wt") as stream:
                stream.write(block + raw)
            self.assertEqual(common_blocks(source, ("MC_ZJETS",)),
                             {bare: block.replace(alias, bare)})
            with gzip.open(source, "wt") as stream:
                stream.write(block + block.replace(alias, bare))
            with self.assertRaises(ValueError):
                common_blocks(source, ("MC_ZJETS",))


if __name__ == "__main__":
    unittest.main()
