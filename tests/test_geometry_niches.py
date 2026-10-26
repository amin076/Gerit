"""Selection and contact-aware relocation regressions for fresh Gerit."""
import math
import json
import random
import tempfile
import unittest
from pathlib import Path
from gerit.adaptive_v3 import StagnationSettings
from gerit.connected_tilings import choose_tilings
from gerit.contact_relocation import propose_contact_relocate
from gerit.fresh_population import make_fresh_population
from gerit.geometry import Packing,Square,validate_packing
from scripts.run_fresh_25 import (run,relative_angle_spread,
                                   select_competitive_diverse)


class GeometryNicheTests(unittest.TestCase):
    def test_orientation_niche_is_geometry_not_ancestry(self):
        # Create a competitive pool with many L=4 aligned layouts, so ordinary
        # elitism fills the quality slots. Rotation must compete in other slots.
        aligned=choose_tilings(12,30,seed=13)
        source=make_fresh_population(12,25,7,2715)
        turned=[x.packing for x in source if relative_angle_spread(x.packing)>.025
                and x.packing.container_side<=4.45]
        self.assertGreaterEqual(len(turned),6)
        pool=[(100+i,item.packing) for i,item in enumerate(aligned)]
        pool += [(200+i,p) for i,p in enumerate(turned)]
        for mode,expected in [('normal',3),('diversify',5)]:
            picked=select_competitive_diverse(pool,25,mode)
            self.assertEqual(len(picked),25)
            self.assertEqual(len({uid for uid,p in picked}),25)
            self.assertLessEqual(min(p.container_side for uid,p in picked),4.)
            angled=sum(relative_angle_spread(p)>.02 for uid,p in picked)
            self.assertGreaterEqual(angled,expected)
            self.assertTrue(all(validate_packing(p,tolerance=0.0).valid for uid,p in picked))
            # Source labels have no role: only geometry and IDs were supplied.

    def test_contact_move_on_non_grid_and_grid(self):
        parents=[choose_tilings(12,1)[0].packing,
                 make_fresh_population(12,25,7,2715)[7].packing]
        for p in parents:
            rng=random.Random(38)
            successes=[]
            for i in range(20):
                child,meta=propose_contact_relocate(p,rng,p.container_side+.5)
                self.assertEqual(meta['action'],'structural_relocate')
                self.assertEqual(meta['move_strategy'],'contact_guided')
                if child:
                    self.assertTrue(validate_packing(child,tolerance=0.0).valid)
                    self.assertLessEqual(child.container_side,p.container_side+.5+1e-9)
                    successes.append(child)
            self.assertGreater(len(successes),0)

    def test_accelerated_phases_really_sample_contact_moves(self):
        # Unlike the normal 30-generation default pilot, this explicitly
        # reaches escape and diversify without running a costly 130 generations.
        with tempfile.TemporaryDirectory() as td:
            report = run(seed=2715, generations=5, directory=Path(td)/'short',
                         make_zip=False,
                         stagnation_settings=StagnationSettings(1, 2, 3, 1e-6))
            attempts=report['structural_move_proposals']
            valid=report['structural_move_valid_children']
            self.assertGreater(attempts.get('contact_guided',0),0)
            self.assertGreater(attempts.get('uniform_relocate',0),0)
            self.assertLessEqual(valid.get('contact_guided',0),attempts['contact_guided'])
            self.assertLessEqual(valid.get('uniform_relocate',0),attempts['uniform_relocate'])
            self.assertGreater(report['mode_generations'].get('escape',0),0)
            self.assertGreater(report['mode_generations'].get('diversify',0),0)
            self.assertTrue((Path(td)/'short'/'verification.json').exists())

    def test_contact_probability_ablation_and_selected_lineage_metrics(self):
        # Same new initial population, same phase schedule and same generation
        # budget; only the structural operator mixture differs. RNG trajectories
        # can diverge, so paired seeds/replicates are still required for claims.
        with tempfile.TemporaryDirectory() as td:
            configs=[]
            for ratio,expected in ((0.0,'uniform_relocate'),(1.0,'contact_guided')):
                folder=Path(td)/f'contact_{ratio}'
                report=run(generations=3,seed=2715,directory=folder,make_zip=False,
                           contact_probability=ratio,
                           stagnation_settings=StagnationSettings(1,2,3,1e-6))
                configs.append(report)
                self.assertEqual(report['contact_probability'],ratio)
                self.assertEqual(report['proposals'],3*25*5)
                self.assertEqual(set(report['structural_move_proposals']),{expected})
                self.assertGreater(report['structural_move_proposals'][expected],0)
                valid=report['structural_move_valid_children'][expected]
                self.assertGreater(report['structural_move_geometry_checks'].get(expected,0),0)
                selected=report['structural_move_selected_children'].get(expected,0)
                self.assertLessEqual(selected,valid)
                self.assertLessEqual(
                    report['structural_move_selected_parent_improving_children'].get(expected,0),
                    selected)
                self.assertEqual(report['mode_generations'],configs[0]['mode_generations'])
                self.assertEqual(report['initial_best_side'],4.0)
                self.assertEqual(report['final_selected_max_positive_overlap_area'],0.0)
                self.assertEqual(report['inherited_parents'],0)
                with (folder/'initial_population.json').open(encoding='utf-8') as f:
                    initial=json.load(f)
                if ratio==0.0: reference_initial=initial
                else: self.assertEqual(initial,reference_initial)
                self.assertEqual(json.loads((folder/'verification.json').read_text())['status'],
                                 'verified')
            for invalid in (-0.01,1.01,float('nan')):
                with self.assertRaises(ValueError):
                    run(generations=1,directory=Path(td)/f'invalid_{invalid}',
                        make_zip=False,contact_probability=invalid)

    def test_one_generation_smoke_counts_guided(self):
        with tempfile.TemporaryDirectory() as td:
            report=run(seed=2708,generations=1,directory=Path(td)/'fresh',make_zip=False,
                       stagnation_settings=None)
            self.assertEqual(report['proposals'],125)
            self.assertEqual(report['initial_best_side'],4.)
            self.assertIn('structural_move_proposals',report)
            self.assertLessEqual(report['best_side'],4.)
            self.assertEqual(report['final_selected_max_positive_overlap_area'],0.)

if __name__=='__main__':unittest.main()