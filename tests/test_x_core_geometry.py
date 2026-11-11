"""Verify analytic X-core motif and independently certified N17 geometry."""
import math
import random
import unittest

from gerit.geometry import validate_packing
from gerit.kaggle import Candidate, validate as interval_validate
from gerit.x_core_geometry import x_core_five_plus_twelve_seed
from scripts.run_symmetry_three_counts import prepare_founders


class XCoreTests(unittest.TestCase):
    def test_17_square_x_core_has_correct_structure_and_is_valid(self):
        p=x_core_five_plus_twelve_seed(17, random.Random(11))
        self.assertEqual(len(p.squares),17)
        self.assertTrue(validate_packing(p,tolerance=0).valid)
        self.assertEqual(sum(abs(s.angle-math.pi/4)<1e-12 for s in p.squares),5)
        self.assertEqual(sum(abs(s.angle)<1e-12 for s in p.squares),12)
        self.assertGreater(p.container_side,4.8284)
        self.assertLess(p.container_side,4.829)
        self.assertLess(p.container_side,5.)
        candidate=Candidate(17,tuple((repr(s.x),repr(s.y),repr(s.angle))
                           for s in p.squares),"analytic_x_core",p.container_side)
        check=interval_validate(candidate)
        self.assertTrue(check.valid, check.reason)

    def test_edge_adjacent_core_and_fourfold_symmetry(self):
        p=x_core_five_plus_twelve_seed(17)
        middle=p.squares[0]
        core=p.squares[1:5]
        u=1/math.sqrt(2)
        for s in core:
            self.assertAlmostEqual(abs(s.x-middle.x),u,delta=2.01e-5)
            self.assertAlmostEqual(abs(s.y-middle.y),u,delta=2.01e-5)
        self.assertEqual(len(core),4)

    def test_five_motif_is_new_founder_not_replacement_for_better_17(self):
        founders=prepare_founders(17,2732,20,5.8,insertion_attempts=5)
        labels=[name for name,_ in founders]
        self.assertIn("x_core_fourfold",labels)
        self.assertIn("four_corner_clusters",labels)
        best=min(p.container_side for _,p in founders)
        self.assertLess(best,4.71)
        self.assertTrue(all(validate_packing(p,tolerance=0).valid for _,p in founders))

    def test_only_17_supported(self):
        for n in (5,9,13,18,19,21):
            self.assertIsNone(x_core_five_plus_twelve_seed(n))
        with self.assertRaises(ValueError):
            x_core_five_plus_twelve_seed(17,clearance=-1)


if __name__=="__main__":
    unittest.main()
