"""Boundary rotated-diamond seeds: construction invariants and geometry."""
import unittest
from scripts.run_boundary_diamonds import (POSITIONS, OFFSETS, seed,
                                          contained, collisions)

class BoundaryDiamondTests(unittest.TestCase):
    def test_single_and_multidiamond_seeds(self):
        for count in (1,2,3,4):
            for name in POSITIONS:
                candidate=seed(name,count,(0,0))
                self.assertIsNotNone(candidate,(name,count))
                packing,moved,side=candidate
                self.assertEqual(len(packing),400+count)
                self.assertTrue(contained(packing))
                self.assertEqual(len(collisions(packing)),0)
                self.assertLessEqual(side,21.0+1e-8)
                self.assertGreaterEqual(moved,0)

    def test_multiple_offsets(self):
        for name in POSITIONS:
            for offset in OFFSETS:
                candidate=seed(name,1,offset)
                self.assertIsNotNone(candidate,(name,offset))
                self.assertEqual(len(candidate[0]),401)

if __name__=="__main__":unittest.main()
