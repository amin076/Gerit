"""Integration checks: advanced founders and archive independence."""
import math
import random
import unittest
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory

from gerit.geometry import validate_packing
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

    def test_registry_conversion_is_optional_and_valid(self):
        stored = grid_solution(5)
        p = from_registry(stored)
        self.assertEqual(p.container_side, 3.0)
        self.assertTrue(validate_packing(p, tolerance=0.0).valid)


if __name__ == "__main__":
    unittest.main()
