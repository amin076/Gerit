"""Regression tests for the 1000-generation image audit: live frontier vs stale grid copies."""
import json
import math
import tempfile
import unittest
from pathlib import Path

from gerit.connected_tilings import choose_tilings
from gerit.fresh_population import make_fresh_population
from gerit.geometry import Square, minimum_bounding_square, validate_packing
from scripts.run_fresh_25 import (
    select_competitive_diverse, is_axis_grid_lattice, relative_angle_spread, run,
)


def crowded_pool():
    # Many different IDs for perfect grid arrangements; many independent,
    # genuinely tilted but valid candidates from fresh, distinct random seeds.
    pool = [(i + 1, p.packing) for i, p in enumerate(choose_tilings(12, 40, seed=13))]
    for j, seed in enumerate((2715, 2716, 2717, 2718)):
        pool.extend((1000 + 100*j + i, m.packing)
                    for i,m in enumerate(make_fresh_population(12,25,7,seed)))
    return pool


class ProgressiveSelectionTests(unittest.TestCase):
    def test_geometry_grid_detector(self):
        p=make_fresh_population(12,25,7,2715)
        self.assertTrue(is_axis_grid_lattice(p[0].packing))
        self.assertTrue(all(not is_axis_grid_lattice(m.packing)
                            for m in p if m.source=='random_rotated'))
        self.assertTrue(all(validate_packing(m.packing,tolerance=0).valid for m in p))

    def test_redundant_grids_age_out_when_competition_exists(self):
        pool=crowded_pool()
        ages={uid:60 for uid,_ in pool if uid < 1000}
        for mode in ('normal','diversify'):
            chosen=select_competitive_diverse(pool,20,mode,incumbent_ages=ages)
            self.assertEqual(len(chosen),20)
            self.assertEqual(len({uid for uid,_ in chosen}),20)
            self.assertLessEqual(sum(is_axis_grid_lattice(p) for _,p in chosen),3)
            self.assertLessEqual(sum(uid<1000 for uid,_ in chosen),4)
            self.assertGreaterEqual(sum(relative_angle_spread(p)>.02 for _,p in chosen),8)
            self.assertTrue(all(p.container_side<5. for _,p in chosen))
            self.assertEqual(min(p.container_side for _,p in chosen),4.)

    def test_protects_non_record_progress_from_a_wide_parent(self):
        grid=choose_tilings(12,1)[0].packing
        def expanded(scale):
            cx=sum(x.x for x in grid.squares)/12
            cy=sum(x.y for x in grid.squares)/12
            return minimum_bounding_square(tuple(
                Square(cx+(q.x-cx)*scale,cy+(q.y-cy)*scale,q.angle)
                for q in grid.squares))
        parent=expanded(1.55)
        child=expanded(1.40)
        self.assertTrue(validate_packing(child,tolerance=0).valid)
        self.assertGreater(parent.container_side,child.container_side)
        self.assertGreater(child.container_side,4.0)
        self.assertLessEqual(child.container_side,5.35)
        pool=crowded_pool()+[(9000,parent),(9001,child)]
        selected=select_competitive_diverse(pool,20,'diversify',
                    incumbent_ages={9000:100},
                    parent_gains={9001:parent.container_side-child.container_side})
        self.assertIn(9001,[uid for uid,_ in selected],
                      'A genuine improving child must compete before stale far-out frontier')
        self.assertNotIn(9000,[uid for uid,_ in selected])

    def test_far_progress_child_renews_a_distant_line_without_static_parent(self):
        grid=choose_tilings(12,1)[0].packing
        def spaced(scale):
            cx=sum(q.x for q in grid.squares)/12
            cy=sum(q.y for q in grid.squares)/12
            return minimum_bounding_square(tuple(Square(
                cx+(q.x-cx)*scale,cy+(q.y-cy)*scale,q.angle)
                for q in grid.squares))
        old=spaced(1.86)
        newer=spaced(1.73)
        self.assertGreater(newer.container_side,6.0)
        self.assertGreater(old.container_side-newer.container_side,.008)
        pool=crowded_pool()+[(9100,old),(9101,newer)]
        selected=select_competitive_diverse(pool,20,'diversify',
                    incumbent_ages={9100:150},
                    parent_gains={9101:old.container_side-newer.container_side})
        chosen={uid for uid,_ in selected}
        self.assertIn(9101,chosen)
        self.assertNotIn(9100,chosen)
        self.assertEqual(len(chosen),20)

    def test_large_static_outlier_does_not_survive_just_for_novelty(self):
        pool=crowded_pool()
        grid=choose_tilings(12,1)[0].packing
        distant=minimum_bounding_square(tuple(
            Square(s.x*1.9,s.y*1.9,s.angle) for s in grid.squares))
        self.assertGreater(distant.container_side,6.)
        pool.append((9999,distant))
        chosen=select_competitive_diverse(pool,20,'diversify',
                   incumbent_ages={9999:500})
        self.assertNotIn(9999,[uid for uid,_ in chosen])
        self.assertLessEqual(max(p.container_side for _,p in chosen),5.15)

    def test_one_generation_twenty_parents_new_diagnostics_and_full_validation(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'fresh20'
            summary=run(squares=12,population=20,structural_seeds=6,
                        seed=2715,generations=1,directory=out,make_zip=False)
            self.assertEqual(summary['proposals'],100)
            self.assertEqual(summary['population'],20)
            self.assertEqual(summary['inherited_parents'],0)
            self.assertGreaterEqual(summary['selected_parent_improving_children'],0)
            self.assertLessEqual(summary['selected_parent_improving_children'],
                                 summary['final_improving_children'])
            self.assertLessEqual(summary['final_axis_grid_parent_count'],20)
            self.assertTrue((out/'verification.json').exists())
            history=[json.loads(l) for l in (out/'generations.jsonl').read_text().splitlines()]
            self.assertIn('axis_grid_parent_count',history[-1])
            self.assertIn('stale_20_parent_count',history[-1])
            self.assertEqual(json.loads((out/'verification.json').read_text())['status'],'verified')

if __name__=='__main__':
    unittest.main()