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

    def test_integrated_coordinated_compression(self):
        from gerit.config import RunConfig, SelectionGroup
        from gerit.evolution import evolve
        config=RunConfig(initial_population=3,next_generation_population=4,
            offspring_per_parent=1,max_generations=2,max_evaluations=20,
            selection_groups=(SelectionGroup("fitness",.75),
                              SelectionGroup("diversity",.25)),
            seed=51)
        result=evolve(config,coordinated=True,compression=True)
        self.assertEqual(len(result.history),3)
        self.assertTrue(validate_packing(result.best,tolerance=0.0).valid)

if __name__=="__main__":
    unittest.main()
