"""Verify audit trail and generation PNG count for a short real run."""
import json
import tempfile
import unittest
from pathlib import Path

from gerit.config import RunConfig
from gerit.evolution import evolve

class AuditTests(unittest.TestCase):
    def test_recorded_generations_match_files(self):
        with tempfile.TemporaryDirectory() as td:
            cfg=RunConfig(initial_population=4,next_generation_population=4,
                          offspring_per_parent=1,max_generations=2,
                          max_evaluations=20,seed=5)
            result=evolve(cfg,output_dir=td,image_columns=2)
            folders=list(Path(td).glob("run-*"))
            self.assertEqual(len(folders),1)
            folder=folders[0]
            summary=json.loads((folder/"run_summary.json").read_text())
            generations=[json.loads(s) for s in (folder/"generations.jsonl").read_text().splitlines()]
            people=[json.loads(s) for s in (folder/"individuals.jsonl").read_text().splitlines()]
            images=sorted((folder/"generation_images").glob("gen_*.png"))
            self.assertEqual(summary["completed_generations"],len(result.history)-1)
            self.assertEqual(len(images),len(generations))
            self.assertEqual(len(people),summary["evaluations"])
            self.assertEqual([g["generation"] for g in generations],list(range(len(generations))))
            self.assertTrue(all(len(g["selected_ids"])==4 for g in generations))
            self.assertGreater(summary["elapsed_seconds"],0)
            ids={p["individual_id"] for p in people}
            self.assertTrue(all(set(p["parent_ids"]) <= ids for p in people))
            self.assertEqual(summary["accepted_children"]+summary["rejected_children"]+1,
                             summary["evaluations"])
            self.assertEqual(summary["best_validation"]["valid"],True)
if __name__=="__main__":
    unittest.main()
