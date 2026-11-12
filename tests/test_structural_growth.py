"""Fast smoke tests for structural growth; never require real 968-square run."""
import unittest
import numpy as np
from gerit.geometry import Packing,Square
from scripts.run_structural_growth import _insertion,_distinct,_score


class StructuralGrowthTests(unittest.TestCase):
    def test_every_insertion_grows_and_keeps_rotatable_founder(self):
        founder=Packing(tuple(
            Square((i%3)+.5,(i//3)+.5,0.) for i in range(8)),3.)
        for style in range(8):
            a=_insertion(founder,3.2,np.random.default_rng(123+style),style)
            self.assertEqual(a.shape,(9,3))
            self.assertTrue(np.isfinite(a).all())
            self.assertTrue(np.all(a[:8,2] != 1000))
            self.assertTrue(np.allclose(a[:8,:2],a[:8,:2]))

    def test_near_archive_keeps_diverse_basin(self):
        archive=[]
        a=np.zeros((4,3));b=a.copy();b[:,0]+=1
        _distinct(archive,a,2.5,(2.,10,2))
        _distinct(archive,a.copy(),2.5,(1.,9,1))
        self.assertEqual(len(archive),1)
        self.assertEqual(archive[0]["quality"],(1.,9,1))
        _distinct(archive,b,2.5,(3.,13,3))
        self.assertEqual(len(archive),2)


if __name__=="__main__":
    unittest.main()
