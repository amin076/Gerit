import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from gerit_core import Search, Settings
from examples.quadratic import Quadratic, move_coordinate, jump


class EngineTest(unittest.TestCase):
    def test_adaptive_default_starts_one_and_caps_ten(self):
        settings=Settings()
        self.assertEqual(settings.initial_parents,1)
        self.assertEqual(settings.max_parents,10)
        self.assertEqual(settings.log_every,10)

    def test_domain_progress_display_is_optional(self):
        from examples.square_packing import TwelveSquares
        problem=TwelveSquares()
        self.assertEqual(problem.progress_display(problem.decode({
            "container_side":5.0,
            "squares":[{"x":float(i)+.5,"y":float(j)+.5,"angle":0.0}
                       for j in range(3) for i in range(4)]
        })),"best_L=5.000000000000")

    def test_outputs_and_budget(self):
        with TemporaryDirectory() as directory:
            cfg=Settings(iterations=200,children_per_parent=6,max_parents=3,
                         stagnation_window=10,competition_generations=10,
                         evaluation_budget=2500,checkpoint_every=10,
                         seed=17,output_dir=directory)
            result=Search(Quadratic(),{"coordinate":move_coordinate,"jump":jump},cfg).run()
            self.assertLess(result.best_objective,10)
            self.assertLessEqual(result.evaluations,cfg.evaluation_budget)
            self.assertTrue((Path(directory)/"best.json").is_file())
            self.assertAlmostEqual(json.loads((Path(directory)/"best.json").read_text())["objective"],result.best_objective)
            self.assertTrue((Path(directory)/"run_summary.json").is_file())

    def test_reproducible_seed(self):
        results=[]
        for _ in range(2):
            with TemporaryDirectory() as directory:
                cfg=Settings(iterations=40,children_per_parent=4,max_parents=2,
                             stagnation_window=5,evaluation_budget=150,
                             seed=444,output_dir=directory)
                result=Search(Quadratic(),{"coordinate":move_coordinate},cfg).run()
                results.append((result.best_state,result.best_objective,result.evaluations))
        self.assertEqual(results[0],results[1])


if __name__ == "__main__":
    unittest.main()
