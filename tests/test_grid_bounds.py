"""Grid-side upper bound is constructive, never a hard mathematical lower bound."""
import json
import tempfile
import unittest
from pathlib import Path
from gerit.grid_bounds import grid_bounds, automatic_search_cap, checked_grid
from gerit.geometry import validate_packing
from scripts.make_grid_population import build_grid_input
from scripts.run_adaptive_auto import init_pop, run


class GridBoundTests(unittest.TestCase):
    def test_ceil_sqrt_cases(self):
        for n,k,r in [(1,1,1),(9,3,3),(12,4,3),(16,4,4),
                      (23,5,5),(25,5,5),(26,6,5)]:
            with self.subTest(n=n):
                b=grid_bounds(n)
                self.assertEqual(b.grid_upper_side,k)
                self.assertEqual(b.grid_rows,r)
                self.assertGreaterEqual(k,b.area_lower_side)
                self.assertEqual(checked_grid(n).container_side,k)
                self.assertTrue(validate_packing(checked_grid(n),tolerance=0).valid)

    def test_invalid_counts(self):
        for n in (0,-1,1.5,True):
            with self.assertRaises(ValueError):grid_bounds(n)

    def test_auto_cap_preserves_above_grid_parent_and_margin(self):
        self.assertAlmostEqual(automatic_search_cap([4.006],12,0.15),4.156)
        self.assertAlmostEqual(automatic_search_cap([4.79,4.95],12,0.15),5.10)
        self.assertAlmostEqual(automatic_search_cap([5.01],23,0.15),5.16)
        with self.assertRaises(ValueError): automatic_search_cap([4.0],12,-.1)

    def test_explicit_grid_generator_is_not_discovery(self):
        for n in (12,23,26):
            with self.subTest(n=n):
                data=build_grid_input(n)
                self.assertEqual(data['initialization_kind'],'explicit_known_grid_baseline')
                self.assertEqual(len(data['selected_members']),20)
                self.assertTrue(all(len(m['squares'])==n and m['policy'] for m in data['selected_members']))
                with tempfile.TemporaryDirectory() as d:
                    path=Path(d)/'seed.json'
                    path.write_text(json.dumps(data))
                    pop,sha,selected,policies,global_policy,source_hash,maxid=init_pop(path)
                    self.assertEqual(len(pop),20)
                    self.assertEqual(len(pop[0][1].squares),n)
                    self.assertEqual(maxid,20)
                    self.assertTrue(global_policy)

    def test_explicit_grid_23_one_generation_valid(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'grid23.json'
            source.write_text(json.dumps(build_grid_input(23)))
            summary=run(generations=1,seed=2323,directory=Path(d)/'experiment',
                        make_zip=False,source_file=source)
            self.assertEqual(summary['squares'],23)
            self.assertEqual(summary['grid_baseline']['grid_upper_side'],5)
            self.assertAlmostEqual(summary['side_cap'],5.15)
            self.assertEqual(summary['plot_scale'],'each_packing_actual_side')
            self.assertTrue(summary['known_grid_injected'])
            self.assertLessEqual(summary['best_side'],5)
            self.assertEqual(summary['proposals'],100)
            report=json.loads((Path(d)/'experiment'/'verification.json').read_text())
            self.assertEqual(report['status'],'verified')

if __name__=='__main__':unittest.main()