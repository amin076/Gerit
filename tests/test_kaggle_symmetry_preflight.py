"""Symmetry preflight: cover all historical families before parent selection."""
import math
import random
import unittest
from unittest.mock import patch

from gerit.geometry import validate_packing
from gerit.symmetry_operators import four_corner_cluster_seed
from scripts.audit_kaggle_symmetry import symmetry_candidates, evaluate_one


class SymmetryPreflightTests(unittest.TestCase):
    def test_all_named_symmetries_n17_18_19_20(self):
        required = {"fourfold", "diagonal_pairs", "horizontal", "vertical",
                    "corner_first", "random_sparse"}
        for n in (17, 18, 19, 20):
            candidates = symmetry_candidates(n, seed=2715 + n, copies=2)
            families = {name for name, _ in candidates}
            self.assertTrue(required.issubset(families),
                            f"N={n}: missing {required - families}")
            self.assertTrue(all(len(p.squares) == n and
                                validate_packing(p, tolerance=0).valid
                                for _, p in candidates))

    def test_four_corners_and_center_45_n17(self):
        candidates = symmetry_candidates(17, seed=2715, copies=1)
        p = next(p for name, p in candidates
                 if name == "four_corner_clusters")
        self.assertEqual(len(p.squares), 17)
        self.assertLess(p.container_side, 5)
        rotated = [square for square in p.squares
                   if abs(square.angle - math.pi / 4) < 1e-12]
        self.assertEqual(len(rotated), 1)
        self.assertTrue(validate_packing(p, tolerance=0).valid)

    def test_four_corners_and_center_45_n5(self):
        candidates = symmetry_candidates(5, seed=2715, copies=1)
        p = next(p for name, p in candidates
                 if name == "four_corners_center_45")
        self.assertLess(p.container_side, 3)
        self.assertAlmostEqual(p.squares[-1].angle, math.pi / 4, places=12)

    def test_symmetry_audit_is_not_censored_by_parent_slots(self):
        stored = {"problems": {"17": {"side": 5.0}}}
        offers = []
        def update(path, record, **kwargs):
            offers.append((kwargs["operator"], record["side"]))
            return {"accepted": True}
        with patch("scripts.audit_kaggle_symmetry.read_registry",
                   return_value=stored), patch(
                       "scripts.audit_kaggle_symmetry.propose_improvement",
                       side_effect=update):
            report = evaluate_one(17, 2732, 1, "unused.json", apply=True)
        self.assertGreaterEqual(report["family_count"], 7)
        self.assertTrue(report["updated"])
        self.assertIn("four_corner_clusters", [x["family"]
                        for x in report["families"]])
        self.assertTrue(any(side < 5.0 for _, side in offers))


if __name__ == "__main__":
    unittest.main()
