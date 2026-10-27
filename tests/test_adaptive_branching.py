"""Tests for configurable temporary branching in the existing lineage runner."""
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from gerit.geometry import Packing, Square
from scripts.run_single_lineage import _seed_branches, run


class BranchingSelectionTests(unittest.TestCase):
    def test_five_branch_ceiling_and_regression(self):
        parent=Packing((Square(.5,.5,0),),4.)
        candidates=[(Packing((Square(.5+i*.01,.5,0),),4.+i*.01),{'id':i})
                    for i in range(1,10)]
        args=Namespace(branches=5,children=10,branch_max_regression=.15,
                       branch_min_distance=.00001)
        with patch('scripts.run_single_lineage._distance',
                   side_effect=lambda a,b:abs(a.squares[0].x-b.squares[0].x)):
            branches=_seed_branches(parent,{'id':0},candidates,args)
        self.assertEqual(len(branches),5)
        self.assertEqual(branches[0]['packing'],parent)
        self.assertTrue(any(x['packing'].container_side>parent.container_side
                            for x in branches[1:]))
        self.assertTrue(all(x['packing'].container_side<=4.15 for x in branches))

    def test_not_enough_distinct_seeds(self):
        parent=Packing((Square(.5,.5,0),),4.)
        args=Namespace(branches=5,children=10,branch_max_regression=.15,
                       branch_min_distance=.00001)
        self.assertEqual(len(_seed_branches(parent,None,[(parent,None)],args)),1)

    def test_branch_option_limits_fail_early(self):
        args=Namespace(steps=1,children=10,fps=30,branches=6,
                       stagnation_window=100,branch_generations=100,
                       significant_gain=1e-6,branch_max_regression=.15,
                       branch_min_distance=1e-5,improvement_epsilon=1e-8,
                       cap_margin=.15,contact_probability=.7)
        with self.assertRaisesRegex(ValueError,'branches'):
            run(args)
        args.branches=0
        with self.assertRaisesRegex(ValueError,'branches'):
            run(args)


if __name__=='__main__':
    unittest.main()
