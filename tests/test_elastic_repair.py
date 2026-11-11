"""Check repair diagnostics and read-only behavior."""
import tempfile
import unittest
from pathlib import Path
import numpy as np
from gerit.elastic_repair import feasibility_diagnostics
from scripts.kaggle_best_registry import initialize_registry,read_registry
from scripts.run_elastic_repair import run

class ElasticRepairTests(unittest.TestCase):
    def test_overlap_and_boundary_are_measured(self):
        poses=np.array([[.5,.5,0],[.6,.5,0],[2.5,2.5,0.]])
        d=feasibility_diagnostics(poses,3.0)
        self.assertGreater(d["max_penetration"],0.8)
        self.assertEqual(d["overlap_pairs"],1)
        self.assertGreater(d["max_outside"],0)
    def test_no_report_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"report.json"
            p.write_text("archived")
            with self.assertRaises(FileExistsError):
                run("unused",report=p)
            self.assertEqual(p.read_text(),"archived")
    def test_bank_unchanged_on_dry_run(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"bank.json"
            initialize_registry(p)
            score=read_registry(p)["total_score"]
            result=run(p,n=5,attempts=1,iterations=15,seed=11,
                       report=Path(d)/"repair.json",
                       checkpoint=Path(d)/"near.npz")
            self.assertEqual(read_registry(p)["total_score"],score)
            self.assertFalse(result["applied"])

if __name__=="__main__": unittest.main()
