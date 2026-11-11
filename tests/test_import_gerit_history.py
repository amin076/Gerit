"""Tests for safe historical packing discovery and import."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_kaggle_grid_bank import grid_solution
from scripts.import_gerit_history import candidates_from_document, discover, normalize
from scripts.kaggle_best_registry import initialize_registry, propose_improvement, read_registry


class HistoricalImportTests(unittest.TestCase):
    def test_extract_real_complete_packing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "old" / "best_result.json"
            path.parent.mkdir(parents=True)
            original = grid_solution(5)
            path.write_text(json.dumps({
                "best": {"side": original["side"], "squares": original["squares"]}
            }), encoding="utf-8")
            found = list(discover(tmp, 5))
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0][2]["n"], 5)
            self.assertEqual(found[0][2]["side"], 3.0)

    def test_reject_partial_or_invalid_historical_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "best_result.json"
            path.write_text(json.dumps({"best": {"side": 2.7}}), encoding="utf-8")
            self.assertEqual(list(discover(tmp, 5)), [])
            invalid = grid_solution(5)
            invalid["squares"][1] = dict(invalid["squares"][0])
            path.write_text(json.dumps({"best": invalid}), encoding="utf-8")
            self.assertEqual(list(discover(tmp, 5)), [])

    def test_nonimproving_import_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = Path(tmp) / "registry.json"
            initialize_registry(registry)
            candidate = grid_solution(5)
            outcome = propose_improvement(
                registry, candidate, source="gerit_historical:test",
                experiment_id="test-import", generation=0)
            self.assertFalse(outcome["accepted"])
            self.assertEqual(read_registry(registry)["problems"]["5"]["side"], 3.0)


if __name__ == "__main__":
    unittest.main()
