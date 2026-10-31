"""Tests for exact-in-angle rigid global rotation. Run: python -m unittest discover -s tests -p 'test_global_rotation.py'."""
import math
import random
import unittest
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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

    def test_rotated_contact_grid_is_numerically_valid(self):
        # Exact contacts are common in dense square packings. A rigid
        # transformation cannot physically introduce overlap.
        original=Packing(tuple(Square(x+.5,y+.5) for x in range(4) for y in range(4)),4.)
        for angle in (0.01,0.1,0.31,0.74,1.21):
            c,t=math.cos(angle),math.sin(angle)
            rotated=tuple(Square(q.x*c-q.y*t,q.x*t+q.y*c,q.angle+angle)
                          for q in original.squares)
            from gerit.geometry import minimum_bounding_square
            fitted=minimum_bounding_square(rotated)
            self.assertTrue(validate_packing(fitted,tolerance=1e-10).valid)

    def test_adapter_records_and_recovers_float_contact(self):
        from examples.square_packing import UnitSquares
        problem=UnitSquares(count=10)
        problem.use_global_rotation=True
        result=problem.canonicalize(row(10))
        self.assertAlmostEqual(result.container_side,11/math.sqrt(2),places=8)
        self.assertTrue(problem.feasible(result))
        self.assertEqual(problem.rotation_rejected_genuine,0)

    def test_invalid_overlapping_source_not_repaired(self):
        from examples.square_packing import UnitSquares
        original=Packing((Square(.5,.5),Square(.5,.5)),2.)
        problem=UnitSquares(count=2)
        problem.use_global_rotation=True
        after=problem.canonicalize(original)
        self.assertEqual(after,original)
        self.assertEqual(problem.rotation_rejected_genuine,1)

    def test_fifty_random_packing_optimizations_are_valid(self):
        from examples.square_packing import UnitSquares
        problem=UnitSquares(count=18,initial_side=12)
        problem.use_global_rotation=True
        for seed in range(50):
            initial=problem.initial(random.Random(seed+700))
            self.assertTrue(problem.feasible(initial))
            self.assertEqual(len(initial.squares),18)
        self.assertEqual(problem.rotation_rejected_genuine,0)

    def test_renderer_uses_same_numerical_contract_as_rotation_adapter(self):
        import tempfile
        from examples.packing_visualization import PackingRecorder, render_packing
        # A one-picometre boundary departure is rejected by the strict
        # numerical test but accepted by the documented 1e-10 contract.
        packing=Packing((Square(.5-1e-12,.5),),1.)
        self.assertFalse(validate_packing(packing,tolerance=0.).valid)
        self.assertTrue(validate_packing(packing,tolerance=1e-10).valid)
        with tempfile.TemporaryDirectory() as folder:
            image=Path(folder)/"sample.png"
            with self.assertRaises(ValueError):
                render_packing(image,packing,generation=0,
                               initial_side=2,parents=1,evaluations=1,size=320)
            render_packing(image,packing,generation=0,initial_side=2,
                           parents=1,evaluations=1,size=320,
                           validation_tolerance=1e-10)
            self.assertTrue(image.exists())
            recorder=PackingRecorder(folder,2,width=320,validation_tolerance=1e-10)
            recorder(0,packing,0,1,1)
            recorder.finish()
            self.assertTrue((Path(folder)/"final_packing.png").exists())

    def test_compression_accepts_numerically_valid_rotated_parent(self):
        from gerit.local_compression import compress_valid, CompressionSettings
        # Reproduce the previous run crash: strict SAT rejects a tiny boundary
        # discrepancy while the rotation adapter's 1e-10 contract accepts it.
        packing=Packing((Square(.5-1e-12,.5),),1.)
        self.assertFalse(validate_packing(packing,tolerance=0.).valid)
        self.assertTrue(validate_packing(packing,tolerance=1e-10).valid)
        with self.assertRaises(ValueError):
            compress_valid(packing,random.Random(5),
                           CompressionSettings(attempts_per_child=1),
                           side_cap=2.)
        out,_=compress_valid(packing,random.Random(5),
                            CompressionSettings(attempts_per_child=1),
                            side_cap=2.,validation_tolerance=1e-10)
        self.assertTrue(validate_packing(out,tolerance=1e-10).valid)

    def test_global_rotation_feeds_compressor_without_crashing(self):
        from examples.square_packing import UnitSquares, PackingOperators
        problem=UnitSquares(count=18,initial_side=12)
        problem.use_global_rotation=True
        ops=PackingOperators(validation_tolerance=1e-10)
        for seed in range(10):
            rng=random.Random(3000+seed)
            initial=problem.initial(rng)
            for _ in range(5):
                child=ops.compress(initial,rng,1.)
                self.assertTrue(problem.feasible(child))
                initial=problem.canonicalize(child)
                self.assertTrue(problem.feasible(initial))


if __name__ == "__main__":
    unittest.main()
