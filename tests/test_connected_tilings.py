"""All-axis-aligned connected tiling construction and ancestry integrity."""
import json
import tempfile
import unittest
from pathlib import Path

from gerit.geometry import Packing, Square, validate_packing
from gerit.grid_bounds import grid_bounds
from gerit.connected_tilings import connected_tiling_candidates, choose_tilings
from scripts.make_tiling_population import build_tiling_input
from scripts.run_adaptive_tilings import run


class ConnectedTilingTests(unittest.TestCase):
    def test_expected_grid_sides(self):
        for n,k in ((1,1),(2,2),(9,3),(12,4),(23,5),(26,6),(36,6)):
            with self.subTest(n=n):
                selected=choose_tilings(n,3)
                self.assertGreater(len(selected),0)
                self.assertEqual(selected[0].packing.container_side,float(k))
                for sol in selected:
                    self.assertEqual(len(sol.cells),n)
                    self.assertLessEqual(sol.packing.container_side,k)
                    self.assertTrue(validate_packing(sol.packing,tolerance=0.0).valid)
                    self.assertTrue(all(s.angle == 0.0 for s in sol.packing.squares))

    def test_twelve_requested_profiles_are_reachable(self):
        candidates=connected_tiling_candidates(12)
        patterns={x.row_lengths for x in candidates}
        self.assertIn((4,4,4),patterns)
        self.assertIn((4,4,3,1),patterns)
        self.assertIn((4,4,2,2),patterns)
        self.assertIn((4,3,3,2),patterns)
        self.assertNotIn((5,5,2),patterns)  # side five exceeds tight grid bound
        extended={x.row_lengths for x in connected_tiling_candidates(12,max_extra_side=1)}
        self.assertIn((5,5,2),extended)
        self.assertIn((5,3,2,2),extended)

    def test_selected_three_are_distinct(self):
        result=choose_tilings(12,3)
        self.assertEqual(len(result),3)
        self.assertEqual(len({r.cells for r in result}),3)

    def test_explicit_library_23_and_26(self):
        for n in (23,26):
            with self.subTest(n=n):
                p=build_tiling_input(n)
                self.assertEqual(len(p['selected_members']),20)
                self.assertTrue(p['known_grid_injected'])
                for m in p['selected_members']:
                    self.assertTrue(m['constructive_ancestor'])
                    squares=tuple(Square(**s) for s in m['squares'])
                    self.assertEqual(len(squares),n)
                    self.assertTrue(validate_packing(Packing(squares,m['container_side']),tolerance=0.0).valid)

    def test_one_generation_provenance_and_archive(self):
        source=Path(__file__).resolve().parents[1] / 'data' / 'round15_selected_population_final.json'
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'seeded_experiment'
            summary=run(generations=1,seed=2712,directory=output,make_zip=False,
                        source_file=source,tiling_seeds=3)
            self.assertEqual(summary['constructive_initial_seed_count'],3)
            self.assertEqual(summary['best_side'],4.0)
            self.assertEqual(summary['best_record_origin'],'constructive_seed_or_descendant')
            self.assertEqual(summary['evolved_baseline_before_seed_injection'],
                             summary['best_unseeded_evolutionary_lineage'])
            self.assertEqual(summary['proposals'],100)
            self.assertTrue(json.loads((output/'verification.json').read_text())['status']=='verified')
            after=json.loads((output/'initial_population_after_seeding.json').read_text())
            self.assertEqual(after['imported_parent_count'],17)
            self.assertEqual(len(after['constructive_seeds']),3)
            self.assertEqual(len(after['selected_members']),20)
            survivor=json.loads((output/'selected_population_final.json').read_text())
            self.assertTrue(survivor['known_grid_injected'])
            self.assertTrue(any(m['constructive_ancestor'] for m in survivor['selected_members']))
            self.assertTrue(any(not m['constructive_ancestor'] for m in survivor['selected_members']))
            with (output/'individuals.jsonl').open(encoding='utf-8') as handle:
                initial_log=[json.loads(line) for line in handle]
            initial_log=[row for row in initial_log if row['generation']==0]
            self.assertEqual(len([row for row in initial_log
                                  if row['initialization_origin']=='connected_tiling_seed']),3)

    def test_invalid_parameters(self):
        for n in (0,-1,1.2):
            with self.assertRaises(ValueError):choose_tilings(n,3)
        with self.assertRaises(ValueError):choose_tilings(12,-1)
        with self.assertRaises(ValueError):choose_tilings(12,3,max_extra_side=-1)


if __name__=='__main__':unittest.main()