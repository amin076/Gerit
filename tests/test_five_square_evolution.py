"""Prove corner-center seed enters Gerit's actual generations and archive."""
import json
import math
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from gerit.config import load_config
from gerit.evolution import evolve
from gerit.geometry import validate_packing
from experiments.five_squares.optimizer import corner_center_seed
from scripts.run_five_square_evolution import corner_center_mutation


class RealEvolutionFiveTests(unittest.TestCase):
    def test_breeding_has_real_generations_and_valid_provenance(self):
        cfg=replace(load_config("configs/five-squares.json"),
                    initial_population=5,next_generation_population=5,
                    offspring_per_parent=2,max_generations=3,seed=2715)
        with tempfile.TemporaryDirectory() as tmp:
            result=evolve(cfg,output_dir=tmp,coordinated=True,
                          initial_seed=corner_center_seed(),
                          structural_mutator=corner_center_mutation,
                          structural_probability=1.0)
            self.assertEqual([h.generation for h in result.history],[0,1,2,3])
            self.assertEqual(len(result.best.squares),5)
            self.assertTrue(validate_packing(result.best,tolerance=0).valid)
            self.assertLess(result.best.container_side,3.)
            self.assertLess(result.history[-1].best_side,result.history[0].best_side)
            folders=list(Path(tmp).glob("run-*"))
            self.assertEqual(len(folders),1)
            folder=folders[0]
            history=[json.loads(x) for x in (folder/"generations.jsonl").read_text().splitlines()]
            self.assertEqual(len(history),4)
            self.assertEqual(history[0]["generation"],0)
            individuals=[json.loads(x) for x in (folder/"individuals.jsonl").read_text().splitlines()]
            self.assertTrue(any(x.get("origin")=="offspring" and
                         x.get("mutation",{}).get("operator")=="custom_coordinated_structural_mutation"
                         for x in individuals if isinstance(x.get("mutation"),dict)))
            summary=json.loads((folder/"run_summary.json").read_text())
            self.assertEqual(summary["completed_generations"],3)
            self.assertGreater(summary["structural_operator_proposals"],0)

    def test_sparse_images_keep_all_generations(self):
        cfg=replace(load_config("configs/five-squares.json"),
                    initial_population=5,next_generation_population=5,
                    offspring_per_parent=2,max_generations=4,seed=2716)
        with tempfile.TemporaryDirectory() as tmp:
            result=evolve(cfg,output_dir=tmp,coordinated=True,
                          initial_seed=corner_center_seed(),
                          structural_mutator=corner_center_mutation,
                          image_every=3)
            run_dir=next(Path(tmp).glob("run-*"))
            history=(run_dir/"generations.jsonl").read_text().splitlines()
            self.assertEqual(len(history),5)
            images=sorted(p.name for p in (run_dir/"generation_images").glob("*.png"))
            self.assertEqual(images,["gen_000.png","gen_003.png","gen_004.png"])
            self.assertEqual(len(result.history),5)
            report=json.loads((run_dir/"run_summary.json").read_text())
            self.assertEqual(report["population_image_every"],3)

    def test_bad_image_stride_rejected(self):
        cfg=replace(load_config("configs/five-squares.json"),
                    initial_population=5,next_generation_population=5,
                    max_generations=1)
        with self.assertRaises(ValueError):
            evolve(cfg,initial_seed=corner_center_seed(),image_every=0)

    def test_seed_and_structural_operator_individually_valid(self):
        seed=corner_center_seed()
        import random
        for _ in range(10):
            candidate=corner_center_mutation(seed,random.Random(_))
            self.assertTrue(validate_packing(candidate,tolerance=0).valid)


if __name__=="__main__":
    unittest.main()
