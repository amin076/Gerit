"""Strict collision, generality and integration tests for three geometry proposals."""
import math
import random
import unittest

from gerit.geometry import Square, Packing, grid_baseline, validate_packing
from gerit.symmetry_operators import four_corner_cluster_seed
from gerit.cluster_geometry_operators import (
    propose_cluster_compaction, propose_symmetry_break,
    propose_incremental_insertion, build_incremental_founder)
from scripts.run_symmetry_three_counts import prepare_founders


class ClusterGeometryTests(unittest.TestCase):
    def test_cluster_move_returns_only_valid_same_n_candidates(self):
        for n in (12,17,18,19):
            source=grid_baseline(n)
            for seed in (5,19):
                p=propose_cluster_compaction(source,random.Random(seed),5.8,
                                             attempts=10)
                if p is not None:
                    self.assertEqual(len(p.squares),n)
                    self.assertLessEqual(p.container_side,5.8+1e-9)
                    self.assertTrue(validate_packing(p,tolerance=0).valid)

    def test_break_symmetry_returns_only_valid_same_n_candidates(self):
        for n in (12,17,18,19):
            source=grid_baseline(n)
            p=propose_symmetry_break(source,random.Random(17),5.8,attempts=15)
            if p is not None:
                self.assertEqual(len(p.squares),n)
                self.assertTrue(validate_packing(p,tolerance=0).valid)

    def test_insertion_supports_arbitrary_n_and_no_forged_square(self):
        for n in (4,9,17):
            source=grid_baseline(n)
            candidate=propose_incremental_insertion(
                source,random.Random(23),n+1,source.container_side+2,
                attempts=15)
            if candidate is not None:
                self.assertEqual(len(candidate.squares),n+1)
                self.assertTrue(validate_packing(candidate,tolerance=0).valid)
        source=four_corner_cluster_seed(17,random.Random(11))
        self.assertIsNotNone(source)
        candidate=build_incremental_founder(
            18,random.Random(26),6.0,sources=(source,),attempts=12)
        if candidate is not None:
            self.assertEqual(len(candidate.squares),18)
            self.assertTrue(validate_packing(candidate,tolerance=0).valid)

    def test_bad_source_rejected(self):
        bad=Packing(tuple(Square(.5,.5) for _ in range(3)),2.)
        with self.assertRaises(ValueError):
            propose_incremental_insertion(bad,random.Random(1),4,4.,attempts=1)
        self.assertIsNone(propose_incremental_insertion(
            grid_baseline(5),random.Random(1),4,4.,attempts=10))

    def test_founders_new_operator_flag_and_validity(self):
        for n in (17,18,19):
            founded=prepare_founders(n,2715+n,20,5.8,insertion_attempts=10)
            self.assertTrue(founded)
            self.assertTrue(all(len(p.squares)==n and
                                validate_packing(p,tolerance=0).valid
                                for _,p in founded))


if __name__=="__main__":
    unittest.main()
