import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from examples.square_packing import TwelveSquares, PackingOperators
from gerit_core import Search, Settings

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
if __name__ == "__main__":
    unittest.main()
