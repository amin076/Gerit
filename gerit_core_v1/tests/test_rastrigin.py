import math
import unittest
from examples.rastrigin_benchmark import Rastrigin, local, coordinated, jump, relocation


class RastriginTest(unittest.TestCase):
    def test_known_global_minimum(self):
        problem=Rastrigin()
        self.assertTrue(problem.feasible([0.,0.]))
        self.assertAlmostEqual(problem.evaluate([0.,0.]),0.,places=12)
        self.assertGreater(problem.evaluate([1.,1.]),0.)

    def test_many_wells(self):
        p=Rastrigin()
        for x,y in ((-2,0),(-1,0),(0,0),(1,0),(2,0)):
            p.evaluate([float(x),float(y)])
        self.assertEqual(len(p.basins),5)

    def test_mutations_and_serialization(self):
        import random
        p=Rastrigin()
        for op in (local,coordinated,jump,relocation):
            state=op([1.,1.],random.Random(7),1.)
            self.assertEqual(len(state),2)
            self.assertEqual(p.decode(p.encode(state)),state)


if __name__=='__main__':
    unittest.main()
