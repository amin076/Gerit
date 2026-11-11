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
from scripts.run_kaggle_advanced_batch import fresh_founder, from_registry, run_one, independent_founder, independent_founders, released_rotation_founder, expanded_founder
from gerit.evolution import packing_distance


class AdvancedBankIntegrationTests(unittest.TestCase):
    def test_n5_geometry_45_degree_center(self):
        p = fresh_founder(5, "auto", random.Random(9))
        self.assertEqual(len(p.squares), 5)
        self.assertTrue(validate_packing(p, tolerance=0.0).valid)
        self.assertAlmostEqual(abs(p.squares[4].angle), math.pi / 4, places=10)
        self.assertLess(p.container_side, 3.0)

    def test_expanded_start_changes_geometry_not_square_size(self):
        for n in (6, 8, 12, 14):
            original = grid_baseline(n)
            raised = expanded_founder(original, 0.8)
            self.assertEqual(len(raised.squares), n)
            self.assertTrue(validate_packing(raised, tolerance=0.0).valid)
            self.assertGreater(raised.container_side, original.container_side + 0.5)
            self.assertEqual([s.angle for s in raised.squares],
                             [s.angle for s in original.squares])
            self.assertEqual(expanded_founder(original, 0), original)

    def test_expanded_start_rejects_bad_parameter(self):
        with self.assertRaises(ValueError):
            expanded_founder(grid_baseline(8), -0.1)

    def test_released_rotations_are_valid_and_not_frozen(self):
        for n in (6, 7, 8, 10):
            original = grid_baseline(n)
            candidate = released_rotation_founder(original, 451 + n)
            self.assertIsNotNone(candidate)
            self.assertTrue(validate_packing(candidate, tolerance=0.0).valid)
            self.assertTrue(any(abs(math.sin(2 * sq.angle)) > 1e-6
                                for sq in candidate.squares))
            self.assertGreater(packing_distance(original, candidate), 1e-7)
            self.assertLessEqual(candidate.container_side,
                                 original.container_side + 0.75)

    def test_two_parent_start_contains_rotated_explorer(self):
        for n in (6, 7, 8, 10):
            first = fresh_founder(n, "auto", random.Random(20261113+n))
            label, second = independent_founder(n, first, 20261113+n+100000)
            self.assertEqual(label, "released_rotations")
            self.assertTrue(any(abs(math.sin(2 * sq.angle)) > 1e-6
                                for sq in second.squares))

    def test_six_independent_founders_small_n(self):
        for n in (8, 12, 14):
            first = fresh_founder(n, "auto", random.Random(n))
            extras = independent_founders(n, first, 9000 + n, 5)
            self.assertGreaterEqual(len(extras), 2)
            packings = [first] + [packing for _, packing in extras]
            for p in packings:
                self.assertEqual(len(p.squares), n)
                self.assertTrue(validate_packing(p, tolerance=0.0).valid)
            for i, a in enumerate(packings):
                for b in packings[i + 1:]:
                    self.assertGreater(packing_distance(a, b), 1e-7)

    def test_founder_count_does_not_exceed_requested(self):
        first = grid_baseline(10)
        self.assertEqual(independent_founders(10, first, 17, 0), [])
        self.assertLessEqual(len(independent_founders(10, first, 17, 3)), 3)

    def test_second_founder_is_not_a_copy(self):
        first = fresh_founder(5, "auto", random.Random(9))
        name, second = independent_founder(5, first, 10205)
        self.assertIsNotNone(name)
        self.assertIsNotNone(second)
        self.assertGreater(packing_distance(first, second), 1e-7)
        self.assertTrue(validate_packing(second, tolerance=0.0).valid)

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
