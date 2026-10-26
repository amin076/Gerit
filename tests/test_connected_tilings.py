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

    def test_seed_injection_resets_incompatible_rolling_history(self):
        """Regression for Round21 -> Round22 (4.00499 -> constructed 4.0)."""
        source=Path(__file__).resolve().parents[1] / 'data' / 'round15_selected_population_final.json'
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            payload=json.loads(source.read_text(encoding='utf-8'))
            old_best=min(float(m['container_side']) for m in payload['selected_members'])
            self.assertGreater(old_best,4.0)
            old_history=[old_best]*81
            payload['stagnation_state']={
                'reference_side':old_best,'last_significant_generation':50,
                'elapsed_generations':100,
                'progress':{'recent_best':old_history,'weak_progress_streak':20,
                            'rolling_window_gain':0.0,'history_source':'v4_stored_state'}}
            old_file=folder/'selected_population_final.json'
            old_file.write_text(json.dumps(payload),encoding='utf-8')
            with (folder/'generations.jsonl').open('w',encoding='utf-8') as f:
                for g,value in enumerate(old_history):
                    f.write(json.dumps({'generation':g,'best_side':value})+'\n')
            result=run(generations=1,seed=2919,directory=folder/'seeded',
                       make_zip=False,source_file=old_file,tiling_seeds=3)
            self.assertEqual(result['initial_best_side'],4.0)
            self.assertEqual(result['progress_reset_reason'],
                             'constructive_seed_improved_initial_best')
            self.assertEqual(result['mode_generations'],{'normal':1})
            self.assertEqual(result['stagnation']['progress']['history_source'],
                             'fresh_after_constructive_seed_injection')
            self.assertEqual(json.loads((folder/'seeded'/'config.json').read_text())
                             ['inherited_stagnation_idle'],0)
            self.assertTrue(json.loads((folder/'seeded'/'verification.json').read_text())
                            ['status']=='verified')
            # Source is not modified, and its original progress history survives.
            self.assertEqual(json.loads(old_file.read_text())['stagnation_state']
                             ['progress']['recent_best'],old_history)

    def test_unseeded_resume_keeps_previous_progress(self):
        source=Path(__file__).resolve().parents[1] / 'data' / 'round15_selected_population_final.json'
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            payload=json.loads(source.read_text(encoding='utf-8'))
            old_best=min(float(m['container_side']) for m in payload['selected_members'])
            payload['stagnation_state']={
                'reference_side':old_best,'last_significant_generation':50,
                'elapsed_generations':100,
                'progress':{'recent_best':[old_best]*81,'weak_progress_streak':20,
                            'rolling_window_gain':0.0}}
            old_file=folder/'selected_population_final.json'
            old_file.write_text(json.dumps(payload),encoding='utf-8')
            result=run(generations=1,seed=2920,directory=folder/'no_seeds',
                       make_zip=False,source_file=old_file,tiling_seeds=0)
            self.assertIsNone(result['progress_reset_reason'])
            self.assertEqual(result['progress_history_source'],'v4_stored_state')
            self.assertEqual(result['mode_generations'],{'escape':1})
            self.assertEqual(json.loads((folder/'no_seeds'/'config.json').read_text())
                             ['inherited_stagnation_idle'],50)
            self.assertTrue(json.loads((folder/'no_seeds'/'verification.json').read_text())
                            ['status']=='verified')

    def test_invalid_parameters(self):
        for n in (0,-1,1.2):
            with self.assertRaises(ValueError):choose_tilings(n,3)
        with self.assertRaises(ValueError):choose_tilings(12,-1)
        with self.assertRaises(ValueError):choose_tilings(12,3,max_extra_side=-1)


if __name__=='__main__':unittest.main()