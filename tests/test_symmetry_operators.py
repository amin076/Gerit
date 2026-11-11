"""Regression tests for geometry-family founders and real two-parent lineage."""
import json
import math
import random
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from gerit.config import load_config
from gerit.evolution import evolve
from gerit.geometry import grid_baseline, validate_packing
from gerit.symmetry_operators import (OPERATORS, geometry_seed_bank,
    four_corner_cluster_seed, multi_parent_quadrant_crossover)
from scripts.run_symmetry_three_counts import prepare_founders


class SymmetryExperimentTests(unittest.TestCase):
    def test_reusable_operators_return_valid_geometry(self):
        for n in (17,18,19,21,22):
            for operator in OPERATORS:
                p=operator.generate(n,random.Random(11))
                if p is not None:
                    self.assertEqual(len(p.squares),n,operator.name)
                    self.assertTrue(validate_packing(p,tolerance=0).valid,operator.name)

    def test_four_corner_cluster_beats_n17_grid_without_reference_answer(self):
        p=four_corner_cluster_seed(17,random.Random(21))
        self.assertIsNotNone(p)
        self.assertTrue(validate_packing(p,tolerance=0).valid)
        self.assertLess(p.container_side,5.0)
        self.assertGreater(p.container_side,math.sqrt(17))

    def test_founder_bank_contains_competitive_17_geometry(self):
        founders=prepare_founders(17,2715,20,5.8)
        self.assertTrue(any(name=='four_corner_clusters' and p.container_side<5
                            for name,p in founders))
        self.assertTrue(all(validate_packing(p,tolerance=0).valid for _,p in founders))

    def test_two_parent_hook_and_audited_ancestry(self):
        first=grid_baseline(17)
        special=four_corner_cluster_seed(17,random.Random(12))
        self.assertIsNotNone(special)
        cfg=replace(load_config('configs/five-squares.json'),
                    n_squares=17,initial_container_side=5.,
                    initial_population=3,next_generation_population=3,
                    offspring_per_parent=2,max_generations=2,seed=2715)
        with tempfile.TemporaryDirectory() as tmp:
            r=evolve(cfg,output_dir=tmp,initial_seed=first,
                     initial_seeds=(special,),
                     coordinated=True,
                     multi_parent_mutator=lambda p,q,rng:multi_parent_quadrant_crossover(p,q,rng,5.8),
                     multi_parent_probability=1.,
                     exploration_side_cap=5.8,image_every=2)
            self.assertEqual(len(r.history),3)
            self.assertLess(r.best.container_side,5)
            folder=next(Path(tmp).glob('run-*'))
            logs=[json.loads(t) for t in (folder/'individuals.jsonl').read_text().splitlines()]
            self.assertTrue(any(x['origin']=='geometry_seed' for x in logs))
            generated=[x for x in logs if x['origin']=='offspring']
            self.assertTrue(generated)
            self.assertTrue(all(len(x['parent_ids'])==2 for x in generated))
            self.assertTrue(any(x['mutation']['operator']=='multi_parent_geometry_crossover'
                                for x in generated))
            report=json.loads((folder/'run_summary.json').read_text())
            self.assertEqual(report['additional_initial_seeds'],1)
            self.assertEqual(report['multi_parent_probability'],1.)

    def test_legacy_signature_still_runs(self):
        cfg=replace(load_config('configs/five-squares.json'),
                    initial_population=3,next_generation_population=3,
                    offspring_per_parent=1,max_generations=1,seed=2715)
        r=evolve(cfg,coordinated=True)
        self.assertEqual(len(r.history),2)


if __name__=='__main__':
    unittest.main()
