"""Generic goal-gap and observer regression tests, independent of packing."""
import unittest
from tempfile import TemporaryDirectory
from gerit_core import Search, Settings


class BoundedQuadratic:
    objective_lower_bound=0.
    def initial(self,rng): return [3.]
    def feasible(self,state): return len(state)==1 and -10<=state[0]<=10
    def evaluate(self,state): return state[0]**2
    def distance(self,a,b): return abs(a[0]-b[0])
    def encode(self,state): return list(state)


def reduce(state,rng,intensity):
    state[0]=max(0.,state[0]-0.5)
    return state


class GenericGoalTests(unittest.TestCase):
    def test_goal_gap_progress_and_callback(self):
        with TemporaryDirectory() as folder:
            seen=[]
            def observe(g,state,objective,parents,evaluations):
                seen.append((g,objective,parents,evaluations))
            cfg=Settings(iterations=8,children_per_parent=1,
                population_adjust_interval=2,evaluation_budget=100,
                output_dir=folder,log_every=100)
            engine=Search(BoundedQuadratic(),{'reduce':reduce},cfg,
                          on_generation=observe)
            result=engine.run()
            self.assertEqual(len(seen),9)
            self.assertEqual([x[0] for x in seen],list(range(9)))
            self.assertTrue(all(x['objective']>=0 for x in engine.history
                                if 'objective' in x))
            checks=[e for e in result.events if e['event']=='progress_check']
            self.assertTrue(checks)
            self.assertTrue(all(e['progress_mode']=='bound_fraction' for e in checks))
            self.assertTrue(all(e['goal_gap']>=0 for e in checks))
            self.assertAlmostEqual(result.best_objective,0.)

    def test_lower_bound_only_for_minimize(self):
        with self.assertRaises(ValueError):
            Search(BoundedQuadratic(),{'reduce':reduce},
                   Settings(maximize=True))


if __name__=='__main__':
    unittest.main()
