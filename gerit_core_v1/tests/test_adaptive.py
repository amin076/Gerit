"""Regression tests for gradual adaptation and historical backtracking."""
import unittest
from tempfile import TemporaryDirectory

from gerit_core import Search, Settings
from gerit_core.engine import Candidate, Lineage


class FiniteSteps:
    """A hard local minimum: best state is zero, earlier parents remain interesting."""
    def initial(self, rng):
        return [4.0]

    def feasible(self, state):
        return len(state) == 1 and -10 <= state[0] <= 10

    def evaluate(self, state):
        return state[0] ** 2

    def distance(self, a, b):
        return abs(a[0] - b[0])

    def encode(self, state):
        return list(state)


def decrement(state, rng, intensity):
    state[0] = max(0., state[0] - 1.)
    return state


class AdaptiveTests(unittest.TestCase):
    def test_history_backtracking_and_stepwise_expansion(self):
        with TemporaryDirectory() as folder:
            cfg=Settings(iterations=18, children_per_parent=2,
                         max_parents=4, population_adjust_interval=2,
                         significant_gain=1e-9, absolute_regression=16.,
                         min_distance=0.1, branch_seed_attempts=4,
                         evaluation_budget=500, output_dir=folder)
            engine=Search(FiniteSteps(),{"decrement":decrement},cfg)
            result=engine.run()
            expand=[e for e in result.events if e["event"]=="population_expand"]
            self.assertTrue(expand, "Must revive historical candidates after a stall")
            self.assertTrue(any(e["source"]=="history" for e in expand))
            self.assertEqual(expand[0]["parents"],2)
            self.assertTrue(all(b["parents"]-a["parents"]==1
                                for a,b in zip(expand,expand[1:])))
            self.assertAlmostEqual(result.best_objective,0.)
            self.assertLessEqual(result.evaluations,cfg.evaluation_budget)

    def test_contraction_is_one_parent_and_rewards_trend(self):
        with TemporaryDirectory() as folder:
            cfg=Settings(max_parents=4, trend_weight=0.8,output_dir=folder)
            engine=Search(FiniteSteps(),{"decrement":decrement},cfg)
            engine.best=Candidate([0.],0.)
            # Strong absolute result vs improving track record must both count.
            engine.parents=[
                Lineage(Candidate([0.],0.),0,[0.,0.,0.]),
                Lineage(Candidate([1.],1.),0,[2.,2.,2.]),
                Lineage(Candidate([3.],9.),0,[0.,0.,0.]),
            ]
            self.assertTrue(engine._contract())
            self.assertEqual(len(engine.parents),2)
            self.assertTrue(any(p.candidate.state==[1.] for p in engine.parents))
            self.assertEqual(engine.events[-1]["event"],"population_contract")

    def test_invalid_ratio_configuration(self):
        with self.assertRaises(ValueError):
            Settings(low_progress_ratio=1.5).validate({"x":decrement})


if __name__=="__main__":
    unittest.main()
