"""Regression tests for saturated-v2 migration, relative credit and escape."""
import copy
import json
import math
import random
import tempfile
import unittest
from pathlib import Path

from gerit.learning import ACTIONS, _zero_policy
from gerit.geometry import Packing, Square, validate_packing
from gerit.adaptive_v3 import (ACTIONS_V3, AdaptiveCreditController, StagnationController,
                           StagnationSettings, normalize_policy,
                           propose_micro, propose_reconfigure)
from scripts.run_adaptive import run, SOURCE


class AdaptivePolicyTests(unittest.TestCase):
    def test_migrates_saturated_v2_without_spurious_new_action_bias(self):
        policy = _zero_policy()
        for ctx in ('open','dense'):
            for a in ACTIONS:
                policy['family'][ctx][a] = -5. if ctx=='dense' else 5.
        for k in policy['sign']:
            policy['sign'][k]=5.
        norm = normalize_policy(policy)
        for ctx in ('open','dense'):
            self.assertTrue(all(abs(x)<1e-12 for x in norm['family'][ctx].values()))
        self.assertTrue(all(abs(x)<1e-12 for x in norm['sign'].values()))
        self.assertEqual(len(norm['family']['dense']),len(ACTIONS_V3))

    def test_retains_relative_information_and_mean_zero(self):
        p = _zero_policy()
        p['family']['dense']['rotate']=4
        p['family']['dense']['translate_x']=-4
        p['size']['rotate']=[-2,1,4]
        n=normalize_policy(p)
        self.assertGreater(n['family']['dense']['rotate'],n['family']['dense']['translate_x'])
        self.assertLess(abs(sum(n['family']['dense'].values())),1e-12)
        self.assertLess(abs(sum(n['size']['rotate'])),1e-12)

    def test_relative_credit_cannot_collapse_to_minus_five(self):
        c = AdaptiveCreditController()
        c.global_policy=normalize_policy(_zero_policy())
        p=c.new_policy()
        meta={'action':'translate_x','context':'dense','size_idx':1,
              'signs':{'x':'x+','y':'y+','rotation':'ccw'}}
        for i in range(1100):
            # 10% differential success makes this family meaningfully distinct.
            good=i%10==0
            p,f=c.update(p,meta,True,0.05 if good else 0.,0.,4.05,12,35,
                         global_best_side=4.0)
        vals=c.global_policy['family']['dense']
        self.assertTrue(all(-3.00001<=v<=3.00001 for v in vals.values()))
        self.assertLess(abs(sum(vals.values())),1e-8)
        self.assertTrue(any(abs(v)>0.0001 for v in vals.values()))
        self.assertNotEqual(len(set(round(v,4) for v in vals.values())),1)

    def test_relative_reward_credits_record(self):
        c=AdaptiveCreditController();p=c.new_policy()
        meta={'action':'rotate','context':'dense','size_idx':1,
              'signs':{'rotation':'ccw'}}
        _,f=c.update(p,meta,True,.002,0.,4.005,10,35,global_best_side=4.004)
        self.assertGreater(f['reward_global_record'],0)
        self.assertGreater(f['reward_competitive'],0)

    def test_train_false_does_not_modify_policy(self):
        c=AdaptiveCreditController();p=c.new_policy()
        before=copy.deepcopy(c.global_policy)
        meta={'action':'single_pose','context':'dense','size_idx':2,'signs':{}}
        _,f=c.update(p,meta,False,0,0,4.0,50,0,train=False)
        self.assertEqual(c.global_policy,before)
        self.assertFalse(f['adaptive_training'])


class StagnationTests(unittest.TestCase):
    def test_thresholds_and_reset_only_for_meaningful_progress(self):
        c=StagnationController(4.005,StagnationSettings(2,4,6,1e-6))
        self.assertEqual(c.update(2,4.005),'precision')
        self.assertEqual(c.update(4,4.005),'escape')
        self.assertEqual(c.update(6,4.005),'diversify')
        self.assertEqual(c.update(7,4.005-1e-9),'diversify')
        self.assertEqual(c.update(8,4.004998),'normal')
        self.assertEqual(c.last_significant_generation,8)

    def test_ops_never_return_invalid(self):
        p=Packing(tuple(Square(i%4+.5,i//4+.5) for i in range(12)),4.)
        for operator in (propose_micro, propose_reconfigure):
            q,meta=operator(p,random.Random(365),5.,attempts=40)
            self.assertIn(meta['action'],ACTIONS_V3)
            if q is not None:
                self.assertTrue(validate_packing(q,tolerance=0).valid)

    def test_all_modes_pipeline_and_archival_verification(self):
        # High threshold on significant improvements deliberately forces all
        # phase transitions; this is an integration test, not a performance claim.
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'adaptive'
            report=run(generations=4,seed=2701,directory=output,source_file=SOURCE,
                       make_zip=False,
                       stagnation_settings=StagnationSettings(1,2,3,100.))
            self.assertEqual(report['proposals'],400)
            self.assertEqual(report['mode_generations'],
                             {'normal':1,'precision':1,'escape':1,'diversify':1})
            self.assertEqual(json.loads((output/'verification.json').read_text())['status'],'verified')
            final=json.loads((output/'selected_population_final.json').read_text())
            self.assertEqual(len(final['selected_members']),20)
            self.assertGreaterEqual(final['stagnation_state']['elapsed_generations'],4)
            self.assertLessEqual(report['best_side'],report['initial_best_side'])
            self.assertIn(report['best_individual_id'],[i['individual_id'] for i in final['selected_members']])
            self.assertEqual(len(list((output/'generation_images').glob('gen_*.png'))),5)

if __name__=='__main__': unittest.main()