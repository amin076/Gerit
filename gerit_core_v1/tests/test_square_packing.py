import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from examples.square_packing import TwelveSquares, PackingOperators
from examples.packing_rotation import rotate_probe,rotation_statistics
from gerit_core import Search, Settings
from examples.packing_visualization import PackingRecorder

class PackingTests(unittest.TestCase):
    def test_initial(self):
        problem = TwelveSquares(initial_side=5.0)
        state = problem.initial(None)
        self.assertTrue(problem.feasible(state))
        self.assertEqual(state.container_side, 5.0)
        self.assertEqual(state, problem.decode(problem.encode(state)))

    def test_moves(self):
        import random
        problem = TwelveSquares()
        state = problem.initial(None)
        actions = PackingOperators(compression_attempts=1)
        for op in (actions.micro, actions.contact, actions.restructure, actions.compress):
            result = op(state, random.Random(7), 1.0)
            self.assertTrue(problem.feasible(result))

    def test_rotated_valid_candidate_from_fresh_start(self):
        import random
        problem=TwelveSquares(initial_side=5.)
        start=problem.initial(None)
        candidate=rotate_probe(start,random.Random(19),1.,attempts=200,cap_margin=.15)
        self.assertTrue(problem.feasible(candidate))
        self.assertGreater(rotation_statistics(candidate)["rotated_squares"],0,
                           "Fresh 5x5 packing should permit genuine rotation")

    def test_orientation_modulo_quarter_turn(self):
        from gerit.geometry import Square, Packing
        packing=Packing((Square(1.,1.,1.5707963267948966),),2.)
        self.assertEqual(rotation_statistics(packing)["rotated_squares"],0)

    def test_saved_geometry(self):
        with TemporaryDirectory() as temp:
            problem = TwelveSquares()
            actions = PackingOperators(compression_attempts=1)
            config = Settings(iterations=3, children_per_parent=2,
                max_parents=2, evaluation_budget=20, population_adjust_interval=2,
                branch_seed_attempts=2, output_dir=temp)
            result = Search(problem, {"compress": actions.compress}, config).run()
            self.assertTrue(problem.feasible(result.best_state))
            state = json.loads((Path(temp)/"best.json").read_text())["state"]
            self.assertTrue(problem.feasible(problem.decode(state)))
            self.assertAlmostEqual(result.best_objective,result.best_state.container_side**2-12.)
            recorder=PackingRecorder(temp,5.0,video=False,width=400)
            recorder(0,result.best_state,result.best_objective,1,result.evaluations)
            recorder.finish()
            self.assertTrue((Path(temp)/"latest_packing.png").is_file())
            self.assertTrue((Path(temp)/"final_packing.png").is_file())
if __name__ == "__main__":
    unittest.main()
