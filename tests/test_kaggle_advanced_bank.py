"""Integration checks: advanced founders and archive independence."""
import math
import random
import unittest
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory

from gerit.geometry import validate_packing, grid_baseline
from gerit.config import RunConfig
from gerit.evolution import evolve
from scripts.build_kaggle_grid_bank import grid_solution
from scripts.kaggle_best_registry import initialize_registry
from scripts.run_kaggle_advanced_batch import fresh_founder, from_registry, run_one


class AdvancedBankIntegrationTests(unittest.TestCase):
    def test_n5_geometry_45_degree_center(self):
        p = fresh_founder(5, "auto", random.Random(9))
        self.assertEqual(len(p.squares), 5)
        self.assertTrue(validate_packing(p, tolerance=0.0).valid)
        self.assertAlmostEqual(abs(p.squares[4].angle), math.pi / 4, places=10)
        self.assertLess(p.container_side, 3.0)

    def test_existing_geometric_founders_multiple_counts(self):
        for n in (6, 7, 8, 10):
            p = fresh_founder(n, "auto", random.Random(n))
            self.assertEqual(len(p.squares), n)
            self.assertTrue(validate_packing(p, tolerance=0.0).valid)

    def test_advanced_engine_best_callback_keeps_original_features(self):
        events = []
        cfg = RunConfig(
            n_squares=5, initial_population=2,
            next_generation_population=2, offspring_per_parent=1,
            initial_container_side=3.0,
            max_generations=1, max_evaluations=200, seed=2917)
        result = evolve(
            cfg, initial_seed=grid_baseline(5), coordinated=True,
            historical_jump_every=20,
            best_callback=lambda packing, generation:
                events.append((generation, packing.container_side)))
        self.assertTrue(events)
        self.assertEqual(events[0][0], 0)
        self.assertLessEqual(result.best.container_side, 3.0)

    def test_registry_conversion_is_optional_and_valid(self):
        stored = grid_solution(5)
        p = from_registry(stored)
        self.assertEqual(p.container_side, 3.0)
        self.assertTrue(validate_packing(p, tolerance=0.0).valid)


if __name__ == "__main__":
    unittest.main()
