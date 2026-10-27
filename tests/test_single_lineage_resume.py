"""Focused source-loading smoke test for single-lineage continuation."""
import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from gerit.adaptive_v4 import AdaptiveCreditController
from gerit.fresh_population import make_fresh_population
from scripts.run_single_lineage import load_start
from gerit.geometry import validate_packing


class SingleLineageResumeTests(unittest.TestCase):
    def test_resume_restores_packing_and_policy(self):
        parent = make_fresh_population(12, 20, 6, 2716)[0].packing
        policy = AdaptiveCreditController().new_policy()
        data = {'container_side': parent.container_side,
                'squares': [vars(s) for s in parent.squares],
                'policy': policy}
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'final_packing.json'
            path.write_text(json.dumps(data), encoding='utf-8')
            args = Namespace(input=None, resume_packing=path,
                             parent_rank=19, squares=12, seed=2716)
            resumed, inherited, global_policy, source = load_start(args)
        self.assertTrue(validate_packing(resumed, tolerance=0.0).valid)
        self.assertAlmostEqual(resumed.container_side, parent.container_side)
        self.assertEqual(resumed.squares, parent.squares)
        self.assertEqual(inherited, policy)
        self.assertIsNone(global_policy)
        self.assertEqual(source['kind'], 'resumed_final_packing')


if __name__ == '__main__':
    unittest.main()
