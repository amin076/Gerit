"""Regression tests for strict downward packing propagation."""
import tempfile
import unittest
from pathlib import Path

from gerit.geometry import grid_baseline
from scripts.kaggle_best_registry import initialize_registry,read_registry
from scripts.run_downward_propagation import _delete_one,run


class DownwardPropagationTests(unittest.TestCase):
    def test_remove_one_square_preserves_valid_size(self):
        packing=grid_baseline(5)
        child,idx=_delete_one(packing)
        self.assertEqual(len(child.squares),4)
        self.assertGreaterEqual(idx,0)
        self.assertLessEqual(child.container_side,packing.container_side)

    def test_dry_run_does_not_edit_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"bank.json"
            initialize_registry(path)
            score=read_registry(path)["total_score"]
            report=run(registry=path,source_n=5,min_n=3,
                       report=Path(directory)/"report.json")
            self.assertEqual(read_registry(path)["total_score"],score)
            self.assertTrue(Path(directory,"report.json").is_file())
            self.assertFalse(report["applied"])

    def test_prevent_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            report=Path(directory)/"report.json"
            report.write_text("unchanged")
            with self.assertRaises(FileExistsError):
                run(registry="unused",report=report)
            self.assertEqual(report.read_text(),"unchanged")


if __name__=="__main__":
    unittest.main()
