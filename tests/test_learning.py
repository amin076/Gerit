import sys
import unittest
import random
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gerit.learning import (ACTIONS,LearningController,LearningSettings,propose_learned)
from gerit.geometry import Square,Packing,validate_packing

class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.ctl=LearningController()
        self.seed=self.ctl.new_policy()
        self.context='open'
        self.proposal={"action":"translate_x", "context":self.context,
                       "size_idx":1, "signs":{"x":"x+","y":"y-","rotation":"cw"}}

    def test_success_is_inherited_and_changes_weight(self):
        oldp=self.ctl.probabilities(self.seed,'open')['translate_x']
        child,signal=self.ctl.update(self.seed,self.proposal,True,0.08,0.0,4.2)
        newp=self.ctl.probabilities(child,'open')['translate_x']
        self.assertTrue(signal['direct_improvement'])
        self.assertGreater(newp,oldp)
        self.assertEqual(self.seed['family']['open']['translate_x'],0.0)
        self.assertGreater(child['size']['translate_x'][1],0.0)
        self.assertGreater(child['sign']['x+'],0.0)
        self.assertGreater(child['sign']['cw'],0.0)

    def test_no_reward_for_valid_non_improver(self):
        new,signal=self.ctl.update(self.seed,self.proposal,True,-0.10,0.,4.2)
        self.assertFalse(signal['final_improvement'])
        self.assertEqual(signal['reward'],0)
        self.assertLess(new['family']['open']['translate_x'],0.)

    def test_invalid_move_penalizes_global_but_not_parent(self):
        self.ctl.update(self.seed,self.proposal,False,0.,0.,4.2)
        self.assertEqual(self.seed['family']['open']['translate_x'],0.0)
        self.assertLess(self.ctl.global_policy['family']['open']['translate_x'],0.)

    def test_compression_credit_is_partial(self):
        raw,meta=self.ctl.update(self.seed,self.proposal,True,-0.003,0.023,4.2)
        self.assertTrue(meta['final_improvement'])
        self.assertFalse(meta['direct_improvement'])
        self.assertGreater(meta['reward'],0.)
        self.assertLess(meta['reward'],0.3)

    def test_epsilon_prevents_elimination(self):
        policy=self.ctl.new_policy()
        policy['family']['open']['rotate']=5
        weights=self.ctl.probabilities(policy,'open')
        self.assertAlmostEqual(sum(weights.values()),1.0)
        self.assertGreaterEqual(min(weights.values()),self.ctl.settings.epsilon_explore/len(ACTIONS))

    def test_sample_on_real_twelve_square_population(self):
        pack=Packing(tuple(Square(0.5+1.15*(i%4),0.5+1.15*(i//4),0.0) for i in range(12)),5.0)
        self.assertTrue(validate_packing(pack,tolerance=0.0).valid)
        rng=random.Random(135)
        for _ in range(30):
            child,meta=propose_learned(pack,rng,5.0,self.seed,self.ctl)
            self.assertIn(meta['action'],ACTIONS)
            if child:
                self.assertEqual(len(child.squares),12)
                self.assertTrue(validate_packing(child,tolerance=0.0).valid)
                self.assertLessEqual(child.container_side,5.0+1e-9)
                self.assertIsInstance(meta['normalized_angle'],float)

if __name__=='__main__':unittest.main()