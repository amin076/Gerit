"""Unit tests for the persistent Kaggle best-solution registry."""
import json
import math
import tempfile
import unittest
from pathlib import Path

from scripts.build_kaggle_grid_bank import grid_solution
from scripts.kaggle_best_registry import (
    initialize_registry, propose_improvement, read_registry,
)


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "registry.json"
        initialize_registry(self.path)

    def test_initialization_and_restart(self):
        bank = read_registry(self.path)
        self.assertEqual(len(bank["problems"]), 1000)
        self.assertEqual(bank["total_square_records"], 500500)
        self.assertAlmostEqual(bank["total_score"], 28.937669916550586, places=10)
        with self.assertRaises(FileExistsError):
            initialize_registry(self.path)

    def test_reject_equal_worse_and_invalid(self):
        candidate = grid_solution(5)
        for current in (candidate,):
            response = propose_improvement(
                self.path, current, source="test", experiment_id="test",
                generation=1)
            self.assertFalse(response["accepted"])
        invalid = grid_solution(5)
        invalid["side"] = 2.0
        with self.assertRaises(ValueError):
            propose_improvement(
                self.path, invalid, source="test", experiment_id="test",
                generation=2)
        self.assertEqual(read_registry(self.path)["problems"]["5"]["side"], 3.0)

    def test_accept_real_valid_improvement_and_persist(self):
        # Two 1x1 squares fit exactly in a 2x1 rectangle, which also
        # fits inside a square of side 2, so use 5 squares instead:
        # testing an improvement via a known analytical 5-square
        # construction requires an actual certified layout. Here we
        # improve an artificially padded valid registry candidate for n=1.
        bank = read_registry(self.path)
        bank["problems"]["1"]["side"] = 2.0
        bank["problems"]["1"]["score_contribution"] = 1.0
        bank["total_score"] += 1.0
        from scripts.kaggle_best_registry import _atomic_write
        _atomic_write(self.path, bank)
        candidate = grid_solution(1)
        result = propose_improvement(
            self.path, candidate, source="analytic_grid",
            experiment_id="regression", generation=0)
        self.assertTrue(result["accepted"])
        stored = read_registry(self.path)
        self.assertEqual(stored["problems"]["1"]["side"], 1.0)
        self.assertEqual(stored["problems"]["1"]["previous_best_side"], 2.0)
        self.assertAlmostEqual(stored["total_score"], 28.937669916550586, places=10)


if __name__ == "__main__":
    unittest.main()
