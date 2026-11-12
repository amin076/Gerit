"""Tests for the first-five-after-each-square campaign launcher."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.run_five_after_squares import groups, run


class FamilyOfFiveTests(unittest.TestCase):
    def test_50_targets_in_ten_disjoint_groups(self):
        plan=groups()
        self.assertEqual(len(plan),10)
        self.assertEqual(plan[0],(22,485,489))
        self.assertEqual(plan[-1],(31,962,966))
        targets=[n for _,lo,hi in plan for n in range(lo,hi+1)]
        self.assertEqual(len(targets),50)
        self.assertEqual(len(set(targets)),50)
        self.assertTrue(all(n<=1000 for n in targets))

    def test_invalid_bounds(self):
        with self.assertRaises(ValueError):
            groups(22,32)
        with self.assertRaises(ValueError):
            groups(22,31,6)

    def test_run_resumes_checkpoint_and_never_passes_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            directory=root/"k22_n485_489"
            directory.mkdir()
            (directory/"sweep_state.json").write_text(json.dumps({
                "next_index":5,
                "results":[{"better":False} for _ in range(5)],
                "projected_score":28.0
            }),encoding="utf-8")
            with patch("scripts.run_five_after_squares.subprocess.run") as mock:
                run(output_root=root,first_k=22,last_k=22)
            args=mock.call_args.args[0]
            self.assertIn("--resume",args)
            self.assertNotIn("--apply",args)
            self.assertEqual(args[args.index("--deep-generations")+1],"200")
            self.assertEqual(args[args.index("--max-n")+1],"489")

    def test_existing_folder_without_checkpoint_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            directory=root/"k22_n485_489"
            directory.mkdir()
            (directory/"my-notes.txt").write_text("preserve")
            with self.assertRaises(FileExistsError):
                run(output_root=root,first_k=22,last_k=22)
            self.assertEqual((directory/"my-notes.txt").read_text(),"preserve")


if __name__=="__main__":
    unittest.main()
