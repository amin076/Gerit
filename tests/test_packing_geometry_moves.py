"""Geometry-only regression tests. Gerit's selection/evolution code is unchanged."""
import math
import random
import unittest

from experiments.five_squares.optimizer import corner_center_seed
from gerit.geometry import validate_packing
from gerit.packing_geometry_moves import propose_pivot_release


class PivotGeometryTests(unittest.TestCase):
    def test_five_square_geometry_can_improve_without_known_solution(self):
        seed=corner_center_seed()
        rng=random.Random(2715)
        children=[propose_pivot_release(seed,rng,3.8) for _ in range(80)]
        valid=[p for p in children if p is not None]
        self.assertTrue(valid)
        self.assertTrue(all(validate_packing(p,tolerance=0).valid for p in valid))
        self.assertLess(min(p.container_side for p in valid),3.0)

    def test_outer_square_rotations_not_frozen(self):
        seed=corner_center_seed()
        rng=random.Random(553)
        children=[propose_pivot_release(seed,rng,3.8) for _ in range(140)]
        valid=[p for p in children if p is not None]
        self.assertTrue(any(abs(p.squares[i].angle)>1e-5
                            for p in valid for i in range(4)))
        self.assertTrue(any(abs(p.squares[4].angle)>1e-5 for p in valid))
        self.assertTrue(any(p.container_side>3 for p in valid))

    def test_validity_guards(self):
        seed=corner_center_seed()
        self.assertIsNone(propose_pivot_release(seed,random.Random(1),0.9))
        self.assertIsNone(propose_pivot_release(seed,random.Random(1),math.inf))


if __name__=="__main__":
    unittest.main()
