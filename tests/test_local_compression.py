import random
import unittest
from gerit.geometry import Square,minimum_bounding_square,validate_packing
from gerit.local_compression import CompressionSettings,compress_valid

class TestLocalCompression(unittest.TestCase):
    def setUp(self):
        self.start=minimum_bounding_square(tuple(
            Square(x,y) for x,y in ((.5,.5),(1.5,.5),(2.5,.5),(.5,1.5),(1.5,1.5))
        ))

    def test_strict_validity_and_never_worse(self):
        for seed in range(10):
            packed,info=compress_valid(self.start,random.Random(seed),
                 CompressionSettings(attempts_per_child=30))
            self.assertTrue(validate_packing(packed,tolerance=0.0).valid)
            self.assertLessEqual(packed.container_side,self.start.container_side+1e-10)
            self.assertEqual(info["compression_trials"],30)

    def test_repeatable(self):
        p,m=compress_valid(self.start,random.Random(919))
        q,n=compress_valid(self.start,random.Random(919))
        self.assertEqual(p,q)
        self.assertEqual(m,n)

if __name__=="__main__":
    unittest.main()
