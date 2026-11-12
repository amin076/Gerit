"""Tests for complete five-after-squares promotion preflight and export gating."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts.finalize_five_after_squares import execute


class FinalizeTests(unittest.TestCase):
    def _root(self,folder):
        for k in range(22,32):
            lo=k*k+1
            p=folder/f"k{k:02d}_n{lo}_{lo+4}"
            p.mkdir()
            (p/"sweep_state.json").write_text(json.dumps({
                "next_index":5,
                "results":[{"n":lo+i} for i in range(5)]}))

    def test_incomplete_checkpoints_prevent_any_registry_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("scripts.finalize_five_after_squares.audit") as auditor:
                with self.assertRaises(FileNotFoundError):
                    execute(root=tmp,registry=Path(tmp)/"bank.json")
                auditor.assert_not_called()

    def test_read_only_preflight_for_all_ten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self._root(root)
            with patch("scripts.finalize_five_after_squares.read_registry",
                       return_value={"total_score":28.0}),\
                 patch("scripts.finalize_five_after_squares.audit",
                       return_value={"verified_better":3,"projected_score":27.99}) as auditor,\
                 patch("scripts.finalize_five_after_squares.build") as builder:
                result=execute(root=root,registry=root/"bank.json")
                self.assertFalse(result["applied"])
                self.assertEqual(auditor.call_count,10)
                self.assertTrue(all(not c.kwargs["apply"] for c in auditor.call_args_list))
                builder.assert_not_called()


if __name__=="__main__":
    unittest.main()
