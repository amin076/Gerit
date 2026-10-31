"""Tests for exact-in-angle rigid global rotation. Run: python -m unittest discover -s tests -p 'test_global_rotation.py'."""
import math
import random
import unittest

from gerit.geometry import Packing, Square, square_vertices, validate_packing
from gerit.global_rotation import optimal_global_rotation


def row(n):
    return Packing(tuple(Square(k + .5, .5, 0.) for k in range(n)), float(n))


def span(packing, theta):
    c, s = math.cos(theta), math.sin(theta)
    vertices = [v for q in packing.squares for v in square_vertices(q)]
    xs = [x * c - y * s for x, y in vertices]
    ys = [x * s + y * c for x, y in vertices]
    return max(max(xs) - min(xs), max(ys) - min(ys))


class GlobalRotationTests(unittest.TestCase):
    def test_ten_square_row_exact_optimum(self):
        packing = row(10)
        result = optimal_global_rotation(packing)
        self.assertAlmostEqual(result.side_after, 11 / math.sqrt(2), places=9)
        self.assertTrue(validate_packing(result.packing, tolerance=1e-9).valid)

    def test_square_grid_cannot_improve(self):
        original = Packing(tuple(Square(x+.5, y+.5) for x in range(2) for y in range(2)), 2.)
        r = optimal_global_rotation(original)
        self.assertAlmostEqual(r.side_after, 2., places=9)

    def test_rigid_pairwise_invariants(self):
        original = Packing(tuple(Square(i*2+.5, (i%2)*2+.5, i*.13) for i in range(5)), 10.)
        r = optimal_global_rotation(original)
        self.assertLessEqual(r.side_after, original.container_side)
        for i, a in enumerate(original.squares):
            b = r.packing.squares[i]
            self.assertAlmostEqual((b.angle-a.angle-r.angle_radians), 0, places=10)
            for j, c in enumerate(original.squares):
                d = r.packing.squares[j]
                self.assertAlmostEqual(math.hypot(a.x-c.x,a.y-c.y),
                                       math.hypot(b.x-d.x,b.y-d.y),places=9)

    def test_matches_dense_angle_grid(self):
        rng = random.Random(1732)
        for _ in range(12):
            squares = tuple(Square(rng.uniform(-2,6),rng.uniform(-2,6),
                                   rng.uniform(0,math.pi/2)) for _ in range(8))
            original = Packing(squares,12.)
            optimum = optimal_global_rotation(original).side_after
            dense = min(span(original,j*math.pi/(2*2000)) for j in range(2001))
            self.assertLessEqual(optimum,dense+1e-8)

    def test_deterministic(self):
        a=optimal_global_rotation(row(10))
        b=optimal_global_rotation(row(10))
        self.assertEqual(a,b)


if __name__ == "__main__":
    unittest.main()
