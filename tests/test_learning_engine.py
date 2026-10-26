"""Public learning-mode engine smoke test (no external run archives)."""
import unittest
from gerit.config import RunConfig,SelectionGroup
from gerit.evolution import evolve
from gerit.geometry import validate_packing

class LearningEngineSmoke(unittest.TestCase):
    def test_evolve_with_inherited_learning(self):
        cfg=RunConfig(
            n_squares=5,initial_population=1,next_generation_population=2,
            offspring_per_parent=1,
            selection_groups=(SelectionGroup('fitness',.9),SelectionGroup('diversity',.1)),
            max_generations=2,max_evaluations=30,
            initial_container_side=3.5,seed=180)
        result=evolve(cfg,learning=True)
        self.assertEqual(len(result.history),3)
        self.assertTrue(validate_packing(result.best,tolerance=0.0).valid)
        self.assertEqual(len(result.best.squares),5)

if __name__=='__main__':
    unittest.main()
