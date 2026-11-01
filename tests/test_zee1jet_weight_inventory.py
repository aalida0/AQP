"""Regression tests for the read-only Zee 1-jet LHE weight audit."""
import gzip
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.audit_zee1jet_weight_inventory import inspect


ALT = [304400, 13000, 25300, 14000, 14100, 14200, 61200,
       42560, 303200, 27400, 331500]


def sample_lhe(missing_event_weight=False):
    scale = [
        f"MUR{mur:.1f}_MUF{muf:.1f}_PDF325100"
        for mur in (0.5, 1.0, 2.0)
        for muf in (0.5, 1.0, 2.0)
        if (mur, muf) != (1.0, 1.0)
    ]
    pdfs = [
        f"MUR1.0_MUF1.0_PDF{pdf}"
        for pdf in list(range(325100, 325201))
        + list(range(93300, 93343)) + ALT
    ]
    labels = scale + pdfs
    assert len(labels) == 163
    header = ['<LesHouchesEvents>', '<header>', '<initrwgt>']
    header += [
        f'<weight id="{i}"> {label} </weight>'
        for i, label in enumerate(labels, 1)
    ]
    header += ['</initrwgt>', '</header>', '<init> </init>']
    body = ['<event>', '3 1 1.0 0 0 0', '<rwgt>']
    for i in range(1, 164 - int(missing_event_weight)):
        body.append(f'<wgt id="{i}"> {float(i):.5e} </wgt>')
    body += ['</rwgt>', '</event>', '</LesHouchesEvents>']
    return "\n".join(header + body) + "\n"


class WeightInventoryTests(unittest.TestCase):
    def test_complete_pmg_reweight_inventory(self):
        with TemporaryDirectory() as temp:
            lhe = Path(temp) / "events.lhe"
            lhe.write_text(sample_lhe())
            report = inspect(lhe)
            self.assertTrue(report["event_level_163_weight_inventory_valid"])
            self.assertEqual(report["event_variation_weight_counts"], [163])
            self.assertEqual(report["category_counts"], {
                "noncentral_scale": 8, "nnpdf31_luxqed": 101,
                "pdf4lhc21_pdfas": 43, "alternative_pdfs": 11,
            })
            self.assertTrue(all(
                report["anti_correlated_scale_weights_present"].values()
            ))

    def test_missing_variation_fails_event_validation(self):
        with TemporaryDirectory() as temp:
            lhe = Path(temp) / "events.lhe"
            lhe.write_text(sample_lhe(missing_event_weight=True))
            report = inspect(lhe)
            self.assertFalse(report["event_level_163_weight_inventory_valid"])
            self.assertEqual(report["event_weight_issues"][0]["missing_count"], 1)

    def test_gzip_input(self):
        with TemporaryDirectory() as temp:
            lhe = Path(temp) / "events.lhe.gz"
            with gzip.open(lhe, "wt") as handle:
                handle.write(sample_lhe())
            self.assertTrue(inspect(lhe)["event_level_163_weight_inventory_valid"])


if __name__ == "__main__":
    unittest.main()
