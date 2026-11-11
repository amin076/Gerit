"""Regression checks for all-square elastic packing growth."""
import tempfile
import unittest
from pathlib import Path

import numpy as np
from gerit.geometry import grid_baseline
from gerit.elastic_growth import ElasticEnergy,initial_growth_pose,relax_once,certified_candidate
from scripts.kaggle_best_registry import initialize_registry,read_registry
from scripts.run_elastic_growth import run


class ElasticGrowthTests(unittest.TestCase):
    def test_gradient_matches_finite_differences(self):
        xy=np.array([[.8,.8],[1.15,.95],[2.15,2.2]])
        angles=np.array([.1,-.2,.16])
        z=np.concatenate((xy.ravel(),angles))
        f=ElasticEnergy(3,3.2,angles,weight=10,angle_weight=.01)
        _,gradient=f(z)
        for i in range(len(z)):
            delta=np.zeros_like(z)
            delta[i]=1e-6
            measured=(f(z+delta)[0]-f(z-delta)[0])/(2e-6)
            self.assertAlmostEqual(float(gradient[i]),float(measured),places=4)

    def test_growth_poses_include_all_angles_and_are_finite(self):
        source=grid_baseline(4)
        poses=initial_growth_pose(source,np.random.default_rng(100),2.99)
        self.assertEqual(poses.shape,(5,3))
        relaxed,loss,steps=relax_once(
            poses,2.99,iterations=8,penalty_schedule=(1,10))
        self.assertEqual(relaxed.shape,(5,3))
        self.assertTrue(np.all(np.isfinite(relaxed)))
        self.assertGreaterEqual(loss,0.)
        self.assertGreater(steps,0)
        candidate=certified_candidate(relaxed,2.99)
        if candidate:
            self.assertEqual(len(candidate.squares),5)

    def test_dry_run_is_not_registry_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            bank=Path(td)/"bank.json"
            initialize_registry(bank)
            original=read_registry(bank)["total_score"]
            result=run(registry=bank,first=5,last=5,attempts=1,
                       iterations=8,report=Path(td)/"dryrun.json",
                       ledger=None,summary=None)
            self.assertEqual(read_registry(bank)["total_score"],original)
            self.assertEqual(result["initial_score"],original)

    def test_refuse_overwrite_before_changes(self):
        with tempfile.TemporaryDirectory() as td:
            report=Path(td)/"old.json"
            report.write_text("original")
            with self.assertRaises(FileExistsError):
                run(registry="unused",report=report,
                    ledger=None,summary=None,apply=True)
            self.assertEqual(report.read_text(),"original")


if __name__=="__main__":
    unittest.main()
