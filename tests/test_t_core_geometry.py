"""Regression and independent interval-SAT checks for three-arm T-core geometry."""
import math
import random
import unittest

from gerit.geometry import validate_packing
from gerit.kaggle import Candidate, validate
from gerit.t_core_geometry import QUADRANTS, t_core_three_arm_seed
from scripts.run_symmetry_three_counts import prepare_founders


class TCoreTests(unittest.TestCase):
    def test_all_four_missing_arm_directions_are_strictly_valid(self):
        for direction in QUADRANTS:
            with self.subTest(direction=direction):
                p=t_core_three_arm_seed(17,random.Random(17),missing_quadrant=direction)
                self.assertEqual(len(p.squares),17)
                self.assertTrue(validate_packing(p,tolerance=0.).valid)
                self.assertEqual(sum(abs(s.angle-math.pi/4)<1e-12 for s in p.squares),4)
                self.assertEqual(sum(abs(s.angle)<1e-12 for s in p.squares),13)
                self.assertGreater(p.container_side,4.8284)
                self.assertLess(p.container_side,4.829)
                self.assertLess(p.container_side,5)
                checked=validate(Candidate(
                    17,tuple((repr(s.x),repr(s.y),repr(s.angle))
                             for s in p.squares),
                    "three_arm_T",p.container_side))
                self.assertTrue(checked.valid, checked.reason)

    def test_three_arms_are_full_edge_adjacent_in_ideal_geometry(self):
        for direction in QUADRANTS:
            p=t_core_three_arm_seed(17,missing_quadrant=direction)
            central=p.squares[0]
            u=1/math.sqrt(2)
            self.assertEqual(len(p.squares[1:4]),3)
            for s in p.squares[1:4]:
                self.assertAlmostEqual(abs(s.x-central.x),u,delta=2.01e-5)
                self.assertAlmostEqual(abs(s.y-central.y),u,delta=2.01e-5)

    def test_in_founder_bank_without_displacing_better_previous_founder(self):
        founders=prepare_founders(17,2732,20,5.8,insertion_attempts=5)
        names=[name for name,_ in founders]
        self.assertIn("t_core_three_arm",names)
        self.assertIn("x_core_fourfold",names)
        self.assertIn("four_corner_clusters",names)
        self.assertLess(min(p.container_side for _,p in founders),4.71)

    def test_rejects_other_n_and_invalid_parameters(self):
        for n in (5,9,16,18,19):
            self.assertIsNone(t_core_three_arm_seed(n))
        with self.assertRaises(ValueError):
            t_core_three_arm_seed(17,missing_quadrant="north")
        with self.assertRaises(ValueError):
            t_core_three_arm_seed(17,clearance=0)


if __name__=="__main__":
    unittest.main()
