"""Regression and integration checks for a fresh, single-pool search."""
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from gerit.fresh_population import make_fresh_population
from gerit.geometry import validate_packing
from gerit.adaptive_v3 import StagnationSettings
from gerit.adaptive_v4 import WindowSettings
from scripts.run_fresh_25 import run, select_competitive_diverse

class FreshRestartTests(unittest.TestCase):
    def test_new_population_is_25_and_source_independent(self):
        pop=make_fresh_population(12,25,7,2715)
        self.assertEqual(len(pop),25)
        self.assertEqual(sum(m.source=='connected_tiling' for m in pop),7)
        self.assertEqual(sum(m.source!='connected_tiling' for m in pop),18)
        self.assertEqual(min(x.packing.container_side for x in pop),4.0)
        self.assertTrue(any(abs(s.angle)>1e-3 for m in pop for s in m.packing.squares))
        self.assertTrue(all(validate_packing(m.packing,tolerance=0.0).valid for m in pop))
        self.assertEqual(pop,make_fresh_population(12,25,7,2715))

    def test_other_counts_and_input_errors(self):
        for n,side in ((23,5),(26,6)):
            with self.subTest(n=n):
                pop=make_fresh_population(n,25,7,2716)
                self.assertEqual(len(pop),25)
                self.assertEqual(min(m.packing.container_side for m in pop),side)
                self.assertTrue(all(len(m.packing.squares)==n for m in pop))
        for args in ((0,25,7),(12,1,1),(12,25,25)):
            with self.assertRaises(ValueError):make_fresh_population(*args)

    def test_label_independent_selection(self):
        pop=make_fresh_population()
        items=[(j+1,m.packing) for j,m in enumerate(pop)]
        a=select_competitive_diverse(items,25,'normal')
        self.assertEqual(len(a),25)
        self.assertEqual(len(set(uid for uid,_ in a)),25)
        self.assertTrue(min(p.container_side for _,p in a)<=4)
        b=select_competitive_diverse(items,25,'diversify')
        self.assertEqual(len(b),25)
        self.assertTrue(all(validate_packing(p,tolerance=0.0).valid for _,p in b))

    def test_one_generation_complete_audit(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'fresh'
            summary=run(generations=1,directory=out,make_zip=True,seed=2708)
            self.assertEqual(summary['population'],25)
            self.assertEqual(summary['proposals'],125)
            self.assertEqual(summary['inherited_parents'],0)
            self.assertFalse(summary['inherited_training'])
            self.assertEqual(summary['initial_best_side'],4.0)
            self.assertEqual(summary['starting_structural_count'],7)
            self.assertEqual(summary['starting_stochastic_count'],18)
            self.assertTrue((out/'complete.zip').is_file())
            self.assertTrue((out/'generation_images.zip').is_file())
            self.assertEqual(json.loads((out/'verification.json').read_text())['status'],'verified')
            initial=json.loads((out/'initial_population.json').read_text())
            self.assertEqual(len(initial['members']),25)
            self.assertEqual(initial['learned_policy_initialization'],'fresh_zero')
            with (out/'individuals.jsonl').open() as f:
                rows=[json.loads(line) for line in f]
            self.assertEqual(len(rows),150)
            self.assertEqual(sum(row['generation']==0 for row in rows),25)
            self.assertTrue(all(row['origin']!='imported_reward_v2_final' for row in rows))
            self.assertTrue(all(all(v==0.0 for v in row['policy']['family']['dense'].values())
                                for row in rows if row['generation']==0))
            with self.assertRaises(FileExistsError):run(generations=1,directory=out,make_zip=False)

    def test_modes_and_generations_are_actual(self):
        with tempfile.TemporaryDirectory() as d:
            summary=run(generations=5,directory=Path(d)/'modes',make_zip=False,seed=2709,
                stagnation_settings=StagnationSettings(1,2,3,1e-6),
                window_settings=WindowSettings(2,1e-4,1,2,3))
            self.assertEqual(summary['proposals'],25*5*5)
            self.assertEqual(sum(summary['mode_generations'].values()),5)
            self.assertGreater(summary['mode_generations'].get('precision',0),0)
            self.assertGreater(summary['mode_generations'].get('escape',0),0)
            self.assertGreater(summary['mode_generations'].get('diversify',0),0)
            self.assertLessEqual(summary['best_side'],4.0)

if __name__ == '__main__':unittest.main()