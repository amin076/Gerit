"""Exact N901 rectangle morph regression checks."""
import unittest
from scripts.plot_901_cluster_morph import build_packing,path_frames,quick_validate,interval_certificate

class Exact901MorphTests(unittest.TestCase):
 def test_all_29_exact_frames(self):
  frames=path_frames()
  self.assertEqual(len(frames),29)
  side=frames[0].packing.container_side
  for f in frames:
   self.assertEqual(len(f.packing.squares),901)
   self.assertEqual(f.packing.container_side,side)
   self.assertTrue(all(s.angle==0 for s in f.packing.squares[:-1]))
   self.assertTrue(quick_validate(f)[0],(f.a,f.b))
  for f in (frames[0],frames[14],frames[-1]):
   ok,reason,_=interval_certificate(f)
   self.assertTrue(ok,reason)
 def test_border_cannot_be_claimed_by_this_model(self):
  for a,b in ((30,15),(29,30),(30,30)):
   with self.assertRaises(ValueError):
    build_packing(a,b)

if __name__=="__main__":unittest.main()
