import math
import unittest
from gerit.geometry import (
    Square, Packing, grid_baseline, minimum_bounding_square, square_inside_container,
    square_vertices, squares_overlap, unused_area, validate_packing
)


class GeometryTests(unittest.TestCase):
    def test_grid_baselines(self):
        for n,L in [(1,1),(2,2),(5,3),(11,4),(17,5)]:
            p=grid_baseline(n)
            self.assertEqual(p.container_side,L)
            self.assertTrue(validate_packing(p).valid)
            self.assertAlmostEqual(unused_area(p),L*L-n)

    def test_unit_edges_when_rotated(self):
        verts=square_vertices(Square(1.2,3.4,math.pi/5))
        for i in range(4):
            self.assertAlmostEqual(math.dist(verts[i],verts[(i+1)%4]),1)

    def test_boundary_contact_allowed(self):
        self.assertFalse(squares_overlap(Square(.5,.5),Square(1.5,.5)))
        self.assertFalse(squares_overlap(Square(.5,.5),Square(1.5,1.5)))
        self.assertTrue(validate_packing(Packing((Square(.5,.5),Square(1.5,.5)),2)).valid)

    def test_overlap_detected_including_rotation(self):
        self.assertTrue(squares_overlap(Square(.5,.5),Square(1.49,.5)))
        self.assertTrue(squares_overlap(Square(1,1),Square(1,1,math.pi/4)))
        result=validate_packing(Packing((Square(.5,.5),Square(.6,.5)),3))
        self.assertEqual(result.overlap_pairs,((0,1),))

    def test_out_of_bounds(self):
        sq=Square(.5,.5,math.pi/4)
        self.assertFalse(square_inside_container(sq,2))
        self.assertEqual(validate_packing(Packing((sq,),2)).outside_indices,(0,))

    def test_minimum_bounding_square(self):
        p=minimum_bounding_square((Square(100.5,-3.5),Square(101.5,-3.5)))
        self.assertAlmostEqual(p.container_side,2)
        self.assertTrue(validate_packing(p).valid)

    def test_bounding_does_not_repair_overlap(self):
        p=minimum_bounding_square((Square(0,0),Square(.1,.1)))
        self.assertFalse(validate_packing(p).valid)
        with self.assertRaises(ValueError):
            unused_area(p)

    def test_bad_input(self):
        with self.assertRaises(ValueError): Square(float("nan"),0)
        with self.assertRaises(ValueError): grid_baseline(0)
        with self.assertRaises(ValueError): squares_overlap(Square(0,0),Square(2,2),tolerance=-1)


if __name__=="__main__":
    unittest.main()
