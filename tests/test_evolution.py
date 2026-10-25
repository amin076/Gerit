"""Integration regression tests for real, seeded, collision-free evolution."""
import tempfile
import unittest
from pathlib import Path
from gerit.config import RunConfig
from gerit.evolution import evolve, packing_distance, select
from gerit.geometry import grid_baseline, validate_packing

class EvolutionTests(unittest.TestCase):
    def test_short_run_reproducible_valid_and_bounded(self):
        cfg=RunConfig(n_squares=5,initial_population=5,next_generation_population=8,
                      offspring_per_parent=2,max_generations=3,max_evaluations=60,seed=31)
        a=evolve(cfg)
        b=evolve(cfg)
        self.assertEqual(a.to_dict(),b.to_dict())
        self.assertEqual(len(a.best.squares),5)
        self.assertTrue(validate_packing(a.best,tolerance=0.0).valid)
        self.assertLessEqual(a.best.container_side,3.0+1e-9)
        self.assertLessEqual(a.evaluations,60)
        self.assertTrue(all(y.best_side<=x.best_side+1e-12
                            for x,y in zip(a.history,a.history[1:])))
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"result.json"
            a.save(path)
            self.assertTrue(path.exists())
            self.assertIn('"validation"',path.read_text())

    def test_selection_and_symmetry(self):
        cfg=RunConfig(next_generation_population=20)
        base=grid_baseline(5)
        self.assertAlmostEqual(packing_distance(base,base),0)
        self.assertEqual(len(select([base],cfg)),20)

    def test_unimplemented_adapter_fails_explicitly(self):
        with self.assertRaises(NotImplementedError):
            evolve(RunConfig(initialization_source="agent",agent_adapter="stub"))

    def test_evaluation_limit(self):
        cfg=RunConfig(initial_population=8,next_generation_population=6,
                      max_evaluations=2,max_generations=20)
        result=evolve(cfg)
        self.assertLessEqual(result.evaluations,2)

if __name__=="__main__":
    unittest.main()
