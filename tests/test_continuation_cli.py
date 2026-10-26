"""End-to-end regression of the public local reward-v2 entry point."""
from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from scripts.run_continuation import run, SOURCE


class TestContinuation(unittest.TestCase):
    def test_one_generation_and_archives(self):
        with tempfile.TemporaryDirectory() as temporary:
            target=Path(temporary)/'one_generation'
            report=run(generations=1,seed=2607,directory=target,source_file=SOURCE)
            self.assertEqual(report['proposals'],100)
            self.assertEqual(report['population'],20)
            self.assertTrue(report['best_side']<=report['initial_best_side'])
            self.assertEqual(len(list((target/'generation_images').glob('gen_*.png'))),2)
            self.assertTrue((target/'verification.json').exists())
            self.assertEqual(json.loads((target/'verification.json').read_text())['status'],'verified')
            final=json.loads((target/'selected_population_final.json').read_text())
            self.assertEqual(len(final['selected_members']),20)
            self.assertIn('global_policy',final)
            self.assertTrue(all('policy' in row for row in final['selected_members']))
            for name in ('complete.zip','generation_images.zip'):
                with ZipFile(target/name) as archive:
                    self.assertIsNone(archive.testzip())
            with ZipFile(target/'generation_images.zip') as archive:
                self.assertEqual(len(archive.namelist()),2)
            # Re-running in the same directory must not silently erase research data.
            with self.assertRaises(FileExistsError):
                run(generations=1,seed=2607,directory=target,source_file=SOURCE)


if __name__=='__main__':
    unittest.main()