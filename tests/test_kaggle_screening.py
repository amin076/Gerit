"""Smoke test for streaming progress in the existing Gerit evolutionary engine."""
import unittest

from gerit.config import RunConfig, SelectionGroup
from gerit.evolution import evolve


class ScreeningEngineTests(unittest.TestCase):
    def test_two_parent_progress_callback(self):
        events = []
        config = RunConfig(
            n_squares=5, initial_population=2,
            next_generation_population=2, offspring_per_parent=1,
            selection_groups=(SelectionGroup("fitness", 0.5),
                              SelectionGroup("diversity", 0.5)),
            max_generations=2, max_evaluations=200,
            initial_container_side=3.0, seed=20261111)
        result = evolve(config, progress_callback=events.append)
        self.assertEqual([event.generation for event in events], [1, 2])
        self.assertEqual(len(result.best.squares), 5)
        self.assertLessEqual(result.best.container_side, 3.0)


if __name__ == "__main__":
    unittest.main()
