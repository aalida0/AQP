"""Test the frozen full-campaign manifest policy without Rucio or Athena."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import aqp_rivet_fresh_full as full


class FreshManifestTests(unittest.TestCase):
    def test_missing_one_wenu_d441_log_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entries = {}
            for sample, task in full.TASKS.items():
                ds = full.production_did(*sample)
                name = f"user.aalida.{task}._000001.EVNT.pool.root"
                entries[ds] = [(name, 1000 if sample[1] == "delta441" else 5000)]
                if sample == ("Wenu", "delta441", "v3"):
                    continue
                folder = root/"logs"/Path(*sample)
                folder.mkdir(parents=True)
                (folder/f"user.aalida.{task}._000001.log.generate").write_text(
                    "Using FxFx cross section recipe: xs = 2 / 1000000\n"
                    "MetaData: cross-section (nb)= 2\n")
            # Add one matched Wenu D441 file so the sample is not empty.
            task = full.TASKS[("Wenu", "delta441", "v3")]
            ds = full.production_did("Wenu", "delta441", "v3")
            entries[ds].append((f"user.aalida.{task}._000002.EVNT.pool.root", 1000))
            folder = root/"logs/Wenu/delta441/v3"
            folder.mkdir(parents=True)
            (folder/f"user.aalida.{task}._000002.log.generate").write_text(
                "Using FxFx cross section recipe: xs = 2 / 1000000\n"
                "MetaData: cross-section (nb)= 2\n")
            out = root/"out"
            manifest = out/"production_manifest.json"
            with patch.multiple(full, OUT=out, MANIFEST=manifest, LOGS=root/"logs",
                                COUNTS=(1,1,1,1,1,1,1,2)), patch.object(
                                    full, "listed_files", side_effect=entries.__getitem__):
                full.prepare()
                doc = json.loads(manifest.read_text())
                sample = doc["samples"]["Wenu/delta441/v3"]
                self.assertEqual(len(sample["included"]), 1)
                self.assertEqual(sample["excluded"][0]["reason"], "MISSING_LOG")
                # An additional missing log in another sample must block preparation.
                (root/"logs/Zee/standard111/v2/user.aalida.53564233._000001.log.generate").unlink()
                with self.assertRaisesRegex(ValueError, "Unexpected exclusions"):
                    full.prepare()
                self.assertEqual(json.loads(manifest.read_text()), doc)

    def test_shards_cover_every_row_once(self):
        rows = list(range(1983))
        chunks = [rows[i::full.SHARDS] for i in range(full.SHARDS)]
        self.assertEqual(sorted(x for chunk in chunks for x in chunk), rows)


if __name__ == "__main__":
    unittest.main()
