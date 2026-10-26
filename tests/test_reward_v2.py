import unittest
from gerit.reward_v2 import CreditController
from gerit.learning import ACTIONS

class CreditTests(unittest.TestCase):
    def setUp(self):
        self.c=CreditController()
        self.p=self.c.new_policy()
        self.proposal={'action':ACTIONS[0],'context':'dense','size_idx':1,
                       'signs':{'x':'x+','y':'y-','rotation':'ccw'}}
    def test_strict_separation(self):
        new,f=self.c.update(self.p,self.proposal,True,0.01,0.02,4.1,5,35)
        self.assertGreater(f['reward_direct'],0)
        self.assertGreater(f['reward_compression'],0)
        self.assertEqual(f['raw_geometry_checks'],5)
        self.assertEqual(f['compression_geometry_checks'],35)
        self.assertGreater(new['family']['dense'][ACTIONS[0]],0)
    def test_compression_only_lower_credit(self):
        _,a=self.c.update(self.p,self.proposal,True,0.,.01,4.1,5,35)
        _,b=self.c.update(self.p,self.proposal,True,.01,0.,4.1,5,35)
        self.assertLess(a['policy_logit_delta'],b['policy_logit_delta'])
    def test_raw_worse_final_still_worse_no_reward(self):
        _,f=self.c.update(self.p,self.proposal,True,-.03,.02,4.1,5,35)
        self.assertEqual(f['reward_direct'],0.0)
        self.assertEqual(f['reward_compression'],0.0)
        self.assertLess(f['policy_logit_delta'],0)
    def test_cost_discourages_equal_gain(self):
        _,a=self.c.update(self.p,self.proposal,True,.02,0.,4.1,2,35)
        _,b=self.c.update(self.p,self.proposal,True,.02,0.,4.1,25,35)
        self.assertGreater(a['reward_direct'],b['reward_direct'])
    def test_freeze_updates_stats_not_weights(self):
        pre=self.c.global_policy['family']['dense'][ACTIONS[0]]
        new,f=self.c.update(self.p,self.proposal,True,.05,.01,4.1,7,35,train=False)
        self.assertEqual(self.c.global_policy['family']['dense'][ACTIONS[0]],pre)
        self.assertEqual(new,self.p)
        self.assertEqual(f['policy_logit_delta'],0)
        self.assertEqual(self.c.proposals,1)
    def test_no_validity_reward(self):
        _,f=self.c.update(self.p,self.proposal,True,0.,0.,4.1,20,35)
        self.assertEqual(f['reward_direct'],0)
        self.assertEqual(f['reward_compression'],0)
        self.assertLess(f['policy_logit_delta'],0)
if __name__=='__main__': unittest.main()