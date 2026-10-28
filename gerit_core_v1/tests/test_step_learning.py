"""Regression checks for generic inheritable step-size policies and warm-start."""
import json
import random
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from gerit_core import Search, Settings
from examples.square_packing import TwelveSquares, PackingOperators


class OneDimensional:
    objective_lower_bound=0.0
    def initial(self,rng): return (3.0,)
    def feasible(self,state): return len(state)==1 and abs(state[0])<100
    def evaluate(self,state): return state[0]**2
    def distance(self,a,b): return abs(a[0]-b[0])
    def encode(self,state): return list(state)


def step(state,rng,intensity):
    return (state[0]-min(state[0],0.04*intensity),)


class StepLearningTests(unittest.TestCase):
    def test_inherited_strategy_derivative_and_jumps(self):
        with TemporaryDirectory() as directory:
            settings=Settings(iterations=12,children_per_parent=4,
                initial_parents=2,max_parents=3,branch_seed_attempts=10,
                evaluation_budget=200,checkpoint_every=4,log_every=20,
                output_dir=directory,seed=88,jump_probability=1.0)
            search=Search(OneDimensional(),{"step":step},settings)
            result=search.run()
            self.assertEqual(result.generations,12)
            self.assertGreater(search.step_stats["jump"]["calls"],0)
            self.assertGreater(sum(search.step_stats[k]["calls"]
                         for k in ("small","medium","large")),0)
            self.assertTrue(all(len(p.step_weights)==3 for p in search.parents))
            self.assertTrue(all(isinstance(p.progress_velocity,float)
                         for p in search.parents))
            status=json.loads((Path(directory)/"status.json").read_text())
            self.assertIn("step_stats",status)
            self.assertIn("progress_acceleration",status["lineages"][0])

    def test_diversity_and_multigeneration_explorer(self):
        from gerit_core.engine import Candidate, Lineage
        with TemporaryDirectory() as directory:
            cfg=Settings(iterations=1,max_parents=3,initial_parents=1,
                         output_dir=directory,diversity_fraction=0.0,
                         max_explorers=1,explorer_generations=4)
            search=Search(OneDimensional(),{"step":step},cfg)
            original=Candidate((1.0,),1.0)
            search.best=original
            search.pool=[original]
            parent=Lineage(original,0,[],step_weights=[1.,1.,1.])
            search.parents=[parent]
            search.generation=10
            duplicate=Candidate((1.0,),1.0)
            self.assertFalse(search._spawn_explorer(duplicate,parent))
            # The exploratory state is worse than the branch baseline but
            # within the allowed global regression allowance.
            worse=Candidate((1.1,),1.1)
            self.assertTrue(search._spawn_explorer(worse,parent))
            self.assertEqual(search.parents[-1].explorer_until,14)
            self.assertEqual(search.parents[-1].explorer_baseline,1.0)
            self.assertEqual(search._population_diversity()["pairs"],1)
            self.assertAlmostEqual(search._population_diversity()["minimum"],0.1)
            self.assertFalse(search._spawn_explorer(Candidate((1.12,),1.12),parent))
            search._contract()
            self.assertEqual(len(search.parents),1)
            self.assertEqual(search.parents[0].candidate, worse)
            self.assertEqual(search.parents[0].explorer_until,14)

    def test_rare_success_survives_stagnation(self):
        from gerit_core.engine import Candidate
        with TemporaryDirectory() as directory:
            cfg=Settings(iterations=1,max_parents=1,output_dir=directory)
            search=Search(OneDimensional(),{"step":step},cfg)
            parent=Candidate((2.0,),4.0)
            lineage=search._new_lineage(parent,0)
            # Successful small step followed by thousands of failures.
            search._step_feedback(lineage,0,parent,Candidate((1.9,),3.61))
            for _ in range(1000):
                search._step_feedback(lineage,0,parent,None)
            for _ in range(1001):
                search._step_feedback(lineage,1,parent,None)
            self.assertEqual(lineage.step_successes,[1,0,0])
            self.assertEqual(lineage.step_attempts,[1001,1001,0])
            self.assertGreater(lineage.step_weights[0],lineage.step_weights[1])
            # An inheriting branch owns an independent copy of the evidence.
            child=search._new_lineage(parent,1,lineage)
            self.assertEqual(child.step_attempts,lineage.step_attempts)
            self.assertEqual(child.step_successes,lineage.step_successes)
            search._step_feedback(child,1,parent,Candidate((1.9,),3.61))
            self.assertEqual(lineage.step_successes[1],0)
            self.assertEqual(child.step_successes[1],1)

    def test_operator_posterior_does_not_collapse_to_equal_floor(self):
        with TemporaryDirectory() as directory:
            cfg=Settings(iterations=1,max_parents=1,output_dir=directory)
            search=Search(OneDimensional(),{"good":step,
                          "idle":lambda state,rng,intensity:state},cfg)
            search.operator_memory["good"]={"attempts":1000,"successes":10}
            search.operator_memory["idle"]={"attempts":1000,"successes":0}
            for name,memory in search.operator_memory.items():
                search.weights[name]=search._success_rate(
                    memory["attempts"],memory["successes"])
            self.assertGreater(search.weights["good"],search.weights["idle"])
            self.assertGreater(search.weights["idle"],0.)

    def test_recent_vs_lifetime_operator_preference(self):
        with TemporaryDirectory() as directory:
            cfg=Settings(output_dir=directory,recent_learning_window=4,
                         recent_learning_mix=0.5)
            search=Search(OneDimensional(),{"step":step},cfg)
            m=search.operator_memory["step"]
            m["attempts"]=100
            m["successes"]=20
            m["utility_sum"]=12.
            m["recent_utilities"]=[0.,0.,0.,0.]
            cold=search._operator_preference("step")
            m["recent_utilities"]=[1.,1.,1.,1.]
            hot=search._operator_preference("step")
            self.assertGreater(hot,cold)
            self.assertGreater(cold,0.)

    def test_cost_and_magnitude_reward(self):
        from gerit_core.engine import Candidate
        with TemporaryDirectory() as directory:
            search=Search(OneDimensional(),{
                "good":lambda state,rng,intensity:(state[0]-.5,),
                "idle":lambda state,rng,intensity:state},
                Settings(output_dir=directory,recent_learning_window=5))
            parent=Candidate((3.,),9.)
            # Force the chooser to select the improving operator.
            search.operators={"good":search.operators["good"]}
            for _ in range(3):
                child=search._mutate(parent)
                self.assertLess(child.score,parent.score)
            memory=search.operator_memory["good"]
            self.assertEqual(memory["successes"],3)
            self.assertGreater(memory["utility_sum"],0.)
            self.assertLess(memory["utility_sum"],3.)
            self.assertEqual(len(memory["recent_utilities"]),3)

    def test_delayed_credit_only_to_origin(self):
        with TemporaryDirectory() as directory:
            search=Search(OneDimensional(),{
                "origin":step,"other":step},Settings(output_dir=directory))
            original=search.weights["origin"]
            other=search.weights["other"]
            search._credit_operator("origin",0.5)
            self.assertGreater(search.weights["origin"],original)
            self.assertEqual(search.weights["other"],other)
            self.assertGreater(search.operator_memory["origin"]["delayed_credit"],0.)
            self.assertEqual(search.operator_memory["origin"]["attempts"],0)

    def test_warm_started_square_remains_valid(self):
        problem=TwelveSquares()
        state=problem.initial(random.Random(4514))
        payload={"state":problem.encode(state)}
        restored=problem.decode(payload["state"])
        self.assertTrue(problem.feasible(restored))
        problem.warm_start=restored
        self.assertEqual(problem.initial(random.Random(20)),restored)
        action=PackingOperators(compression_attempts=1)
        trial=action.scaled_pose(restored,random.Random(33),3.)
        self.assertTrue(problem.feasible(trial))


if __name__=="__main__":
    unittest.main()
