"""Five-square corner/center experiment correctness and reproducibility."""
import math
import unittest

from experiments.five_squares.optimizer import (
    corner_center_seed, arrangement, best_inward_for_angle, search)
from gerit.geometry import validate_packing
from gerit.kaggle import Candidate,validate,baseline_score,puzzle_score


class CornerCenterFiveTests(unittest.TestCase):
    def test_seed_has_exactly_four_corners_plus_center(self):
        seed=corner_center_seed()
        self.assertEqual(len(seed.squares),5)
        self.assertEqual(seed.container_side,3.)
        self.assertEqual([(s.x,s.y,s.angle) for s in seed.squares],[
            (.5,.5,0.),(2.5,.5,0.),(.5,2.5,0.),(2.5,2.5,0.),(1.5,1.5,0.)])
        self.assertTrue(validate_packing(seed,tolerance=0).valid)

    def test_coupled_rotation_and_compression_is_valid(self):
        for angle in (0.02,0.1,0.35,0.70,math.pi/4):
            with self.subTest(angle=angle):
                pack,d=best_inward_for_angle(angle)
                self.assertTrue(validate_packing(pack,tolerance=0).valid)
                self.assertLess(pack.container_side,3)
                self.assertGreater(d,0)
                cand=Candidate(5,tuple((repr(s.x),repr(s.y),repr(s.angle))
                                       for s in pack.squares),"test",pack.container_side)
                checked=validate(cand)
                self.assertTrue(checked.valid,checked.reason)

    def test_new_search_beats_grid_from_unrotated_seed(self):
        run=search(seed=2715,proposals=60)
        self.assertGreater(run.accepted_improvements,0)
        self.assertLess(run.best.container_side,3.)
        self.assertGreater(baseline_score(5)-puzzle_score(5,run.best.container_side),0.)

    def test_repeatable(self):
        a=search(seed=2716,proposals=25)
        b=search(seed=2716,proposals=25)
        self.assertEqual(a.best.container_side,b.best.container_side)
        self.assertEqual(a.trace,b.trace)

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            arrangement(0,0.5)
        with self.assertRaises(ValueError):
            best_inward_for_angle(float("nan"))


if __name__=="__main__":
    unittest.main()
