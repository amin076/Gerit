"""Gap insertion structural and method registry regression tests."""
import math
import tempfile
import unittest
from pathlib import Path
from dataclasses import asdict

from gerit.geometry import Packing,Square,validate_packing
from gerit.gap_insert_geometry import valid_one_more
from scripts.kaggle_best_registry import initialize_registry,propose_improvement,read_registry
from scripts.run_gap_insertion_screen import screen


class GapInsertTests(unittest.TestCase):
    def test_open_pocket_accepts_non_grid_insertion(self):
        source=Packing((Square(.5,.5),Square(2.5,.5),Square(.5,2.5)),3.)
        # All three fit within a 3x3 square, and a fourth can fit.
        best,trials=valid_one_more(source,3.1,seed=99,samples=200)
        self.assertIsNotNone(best)
        self.assertEqual(len(best.squares),4)
        self.assertLess(best.container_side,3.1)
        self.assertTrue(validate_packing(best,tolerance=0).valid)
        self.assertGreater(trials,0)

    def test_dry_run_preserves_bank(self):
        with tempfile.TemporaryDirectory() as folder:
            registry=Path(folder)/"bank.json"
            initialize_registry(registry)
            before=read_registry(registry)["total_score"]
            out=screen(registry,max_n=50,samples=50,
                       apply=False,ledger=None,report=Path(folder)/"report.json")
            self.assertEqual(read_registry(registry)["total_score"],before)
            self.assertEqual(out["initial_score"],before)
            self.assertTrue(Path(folder,"report.csv").exists())

    def test_refuse_report_overwrite_before_bank_touch(self):
        with tempfile.TemporaryDirectory() as folder:
            registry=Path(folder)/"bank.json"
            initialize_registry(registry)
            output=Path(folder)/"report.json"
            output.write_text("original")
            with self.assertRaises(FileExistsError):
                screen(registry,report=output,apply=True,ledger=None)
            self.assertEqual(output.read_text(),"original")


if __name__=="__main__":
    unittest.main()
