import random
import unittest
from gerit.geometry import Square, Packing, minimum_bounding_square, validate_packing
from gerit.adaptive import AdaptiveController, mutate_adaptive

class TestAdaptive(unittest.TestCase):
    def test_feedback_shrinks_steps(self):
        controller = AdaptiveController()
        packing = minimum_bounding_square(tuple(
            Square(x,y) for x,y in ((.5,.5),(1.5,.5),(2.5,.5),(.5,1.5),(1.5,1.5))
        ))
        initial = controller.scales(packing)
        for _ in range(120):
            controller.record(False, "container")
        smaller = controller.scales(packing)
        self.assertLess(smaller[0], initial[0])
        self.assertLess(smaller[1], initial[1])
        for _ in range(120):
            controller.record(True, "valid")
        self.assertGreater(controller.scales(packing)[0], smaller[0])

    def test_density_changes_scale(self):
        controller = AdaptiveController()
        squares = tuple(Square(x,y) for x,y in
                        ((.5,.5),(1.5,.5),(2.5,.5),(.5,1.5),(1.5,1.5)))
        a = minimum_bounding_square(squares)
        b = Packing(a.squares, 2.8)
        self.assertLess(controller.scales(b)[0], controller.scales(a)[0])

    def test_validity_and_record_count(self):
        controller = AdaptiveController()
        rng = random.Random(42)
        packing = minimum_bounding_square(tuple(
            Square(x,y) for x,y in ((.5,.5),(1.5,.5),(2.5,.5),(.5,1.5),(1.5,1.5))
        ))
        for _ in range(120):
            child, meta = mutate_adaptive(packing, rng, 3.0, controller)
            if child:
                self.assertTrue(validate_packing(child, tolerance=0.0).valid)
                self.assertLessEqual(child.container_side, 3.0+1e-9)
            self.assertIn(meta["mode"], ("macro", "adaptive_local"))
        self.assertEqual(controller.attempts, 120)

if __name__ == "__main__":
    unittest.main()
