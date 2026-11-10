"""Contact compaction tests: geometry-only; no engine modifications."""
import json
import math
import random
import unittest
from pathlib import Path
from gerit.geometry import Packing,Square,validate_packing
from gerit.contact_compaction import propose_contact_compaction


class ContactCompactionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        j=json.loads(Path("experiments/five_squares/seed_from_local_2000.json").read_text())
        cls.seed=Packing(tuple(Square(**s) for s in j["squares"]),j["side"])

    def test_seed_is_valid(self):
        self.assertTrue(validate_packing(self.seed,tolerance=0).valid)
        self.assertAlmostEqual(self.seed.container_side,2.7470414077646637,places=12)

    def test_results_valid_and_never_worse(self):
        for seed in (2,7,2715):
            child=propose_contact_compaction(self.seed,random.Random(seed),3.8,attempts=160)
            if child is not None:
                self.assertTrue(validate_packing(child,tolerance=0).valid)
                self.assertLessEqual(child.container_side,self.seed.container_side+1e-10)

    def test_no_single_square_frozen_and_no_answer_injected(self):
        from gerit.packing_geometry_moves import propose_pivot_release
        rng=random.Random(42)
        for _ in range(15):
            initial=propose_pivot_release(self.seed,rng,3.8)
            if initial is None:
                continue
            candidate=propose_contact_compaction(initial,rng,3.8,attempts=60)
            if candidate is not None:
                self.assertTrue(validate_packing(candidate,tolerance=0).valid)
                self.assertLessEqual(candidate.container_side,initial.container_side+1e-10)

    def test_bad_input_rejected(self):
        self.assertIsNone(propose_contact_compaction(self.seed,random.Random(1),float("inf")))
        self.assertIsNone(propose_contact_compaction(self.seed,random.Random(1),3.8,attempts=0))
        invalid=Packing((Square(0.5,0.5),Square(0.5,0.5)),2)
        with self.assertRaises(ValueError):
            propose_contact_compaction(invalid,random.Random(1),3.8)


if __name__=="__main__":
    unittest.main()
