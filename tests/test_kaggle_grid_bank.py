"""Regression tests for the complete grid baseline."""
import math
import unittest

from scripts.build_kaggle_grid_bank import build_bank, grid_solution, validate_grid


class GridBankTests(unittest.TestCase):
    def test_all_problems_and_score(self):
        bank = build_bank()
        self.assertEqual(len(bank["problems"]), 1000)
        self.assertEqual(bank["total_square_records"], 500500)
        self.assertAlmostEqual(bank["total_score"], 28.937669916550586, places=11)
        self.assertEqual(sum(int(math.isqrt(n) ** 2 == n) for n in range(1, 1001)), 31)
        for n in range(1, 1001):
            record = bank["problems"][str(n)]
            self.assertTrue(record["validated"])
            self.assertEqual(len(record["squares"]), n)
            self.assertEqual(record["side"], math.ceil(math.sqrt(n)))

    def test_overlap_rejected(self):
        record = grid_solution(5)
        record["squares"][1] = dict(record["squares"][0])
        with self.assertRaises(ValueError):
            validate_grid(record)

    def test_boundary_rejected(self):
        record = grid_solution(5)
        record["squares"][0]["x"] = -0.5
        with self.assertRaises(ValueError):
            validate_grid(record)


if __name__ == "__main__":
    unittest.main()
