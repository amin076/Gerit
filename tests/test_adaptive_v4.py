"""Regression tests for low-progress windows and measured mode attribution."""
import json
import math
import tempfile
import unittest
from pathlib import Path
from gerit.adaptive_v3 import StagnationSettings
from gerit.adaptive_v4 import ProgressAwareStagnationController,WindowSettings
from scripts.run_adaptive_v4 import run, SOURCE


class RollingProgressTests(unittest.TestCase):
    def settings(self):
        return WindowSettings(80,1e-4,1,20,60)

    def test_repeated_tiny_records_do_not_block_escape(self):
        c=ProgressAwareStagnationController(4.01,StagnationSettings(40,80,120,1e-6),self.settings())
        l=4.01
        modes=[]
        for g in range(1,150):
            if g%10==0: l-=2e-6
            modes.append(c.update(g,l))
        self.assertEqual(modes[79],'precision')
        self.assertEqual(modes[98],'escape')
        self.assertEqual(modes[138],'diversify')
        self.assertLess(c.window_gain,1e-4)
        # A sufficiently large record gain restores a healthy 80-generation slope.
        mode=c.update(150,l-0.0002)
        self.assertEqual(mode,'normal')
        self.assertEqual(c.weak_progress_streak,0)

    def test_restore_v3_adjacent_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'generations.jsonl';l=4.01
            with f.open('w',encoding='utf-8') as h:
                for g in range(101):
                    if g and g%10==0:l-=2e-6
                    h.write(json.dumps({'generation':g,'best_side':l})+'\n')
            c=ProgressAwareStagnationController(l,window_settings=self.settings())
            self.assertEqual(c.restore_progress(None,f),'adjacent_generation_history')
            self.assertEqual(len(c.recent_best),81)
            self.assertEqual(c.weak_progress_streak,21)
            self.assertEqual(c.mode(0),'escape')

    def test_v4_state_preserves_streak_when_resumed(self):
        c=ProgressAwareStagnationController(4.01,window_settings=WindowSettings(4,0.002,1,2,3))
        for g in range(1,10):c.update(g,4.01)
        stored=c.progress_snapshot()
        n=ProgressAwareStagnationController(4.01,window_settings=WindowSettings(4,0.002,1,2,3))
        self.assertEqual(n.restore_progress(stored),'v4_stored_state')
        self.assertEqual(n.weak_progress_streak,c.weak_progress_streak)
        self.assertEqual(n.mode(0),'diversify')
        self.assertEqual(n.update(1,4.01),'diversify')

    def test_full_window_not_inferred_from_single_measurement(self):
        c=ProgressAwareStagnationController(4.01,StagnationSettings(100,200,300,1e-6),self.settings())
        for g in range(1,79):self.assertEqual(c.update(g,4.01),'normal')
        self.assertIsNone(c.window_gain)

    def test_reject_inconsistent_resume_data(self):
        c=ProgressAwareStagnationController(4.01)
        with self.assertRaises(ValueError):c.restore_progress({'recent_best':[4.3]})
        with self.assertRaises(ValueError):c.update(1,float('nan'))

    def test_end_to_end_all_modes_with_accounting(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'result'
            result=run(generations=6,seed=2801,directory=dest,source_file=SOURCE,
                       make_zip=False,stagnation_settings=StagnationSettings(100,200,300,100.),
                       window_settings=WindowSettings(2,100.,1,2,3))
            self.assertEqual(result['mode_generations'],{'normal':2,'precision':1,'escape':1,'diversify':2})
            self.assertEqual(result['proposals'],600)
            self.assertEqual(sum(result['mode_proposals'].values()),600)
            self.assertEqual(sum(result['mode_valid_children'].values()),result['valid_children'])
            self.assertEqual(sum(result['mode_geometry_checks'].values()),result['total_geometry_checks'])
            self.assertTrue((dest/'mode_metrics.json').exists())
            self.assertEqual(json.loads((dest/'verification.json').read_text())['status'],'verified')
            final=json.loads((dest/'selected_population_final.json').read_text())
            self.assertIn('progress',final['stagnation_state'])
            self.assertEqual(len(final['selected_members']),20)
            self.assertLessEqual(result['best_side'],result['initial_best_side'])

if __name__=='__main__':unittest.main()