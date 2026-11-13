import unittest
import numpy as np
from scripts.run_corner45_901_family import corner_founder,overlap_pairs,certify

class CornerFamilyTests(unittest.TestCase):
 def test_corner_901_through_905(self):
  for n in range(901,906):
   for corner in ("upper_right","upper_left"):
    p,stats=corner_founder(n,corner=corner)
    self.assertEqual(len(p),n)
    self.assertEqual(len(overlap_pairs(p)),0)
    self.assertEqual(int(np.count_nonzero(np.abs(p[:,2])>.1)),1)
    self.assertTrue(certify(p,31.0,"test").valid)
    self.assertEqual(stats["added"],n-901)

if __name__=="__main__":unittest.main()
