"""Autonomous family sweep: interval selection, JSON recovery and dry-run tests."""
import json
import tempfile
import unittest
from pathlib import Path

from gerit.packing_io import load_packing_json
from scripts.kaggle_best_registry import initialize_registry,read_registry
from scripts.run_auto_family_sweep import family_targets,run


class AutomaticFamilySweepTests(unittest.TestCase):
    def test_half_interval_targets(self):
        self.assertEqual(list(family_targets(231,240)),list(range(231,241)))
        self.assertEqual(list(family_targets(255,274)),
                         list(range(257,273)))
        self.assertEqual(list(family_targets(2,10)),[2,5,6,10])
        self.assertEqual(list(family_targets(288,295)),
                         list(range(290,296)))

    def test_old_literal_newline_suffix_loads_without_modifying_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"old.json"
            source={"n":2,"side":2.0,"squares":[{"x":.5,"y":.5,"angle":0.},
                                                {"x":1.5,"y":.5,"angle":0.}]}
            legacy=json.dumps(source)+"\\n"
            path.write_text(legacy)
            self.assertEqual(load_packing_json(path),source)
            self.assertEqual(path.read_text(),legacy)
            path.write_text(json.dumps(source)+json.dumps(source))
            with self.assertRaises(ValueError):
                load_packing_json(path)

    def test_two_n_sweep_and_resume_without_modifying_bank(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            registry=folder/"bank.json"
            initialize_registry(registry)
            old=read_registry(registry)["total_score"]
            out=folder/"sweep"
            result=run(registry=registry,output_dir=out,
                       first=5,max_n=6,attempts=1,iterations=8,
                       deep_generations=1,deep_iterations=8,seed=10)
            self.assertEqual(result["completed"],2)
            self.assertEqual(read_registry(registry)["total_score"],old)
            summary=json.loads((out/"sweep_state.json").read_text())
            self.assertEqual(summary["next_index"],2)
            result2=run(registry=registry,output_dir=out,
                        first=5,max_n=6,attempts=1,iterations=8,
                        deep_generations=1,deep_iterations=8,seed=10,
                        resume=True)
            self.assertEqual(result2["completed"],2)

    def test_never_overwrite_existing_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/"sweep"
            out.mkdir()
            with self.assertRaises(FileExistsError):
                run(registry="does-not-matter",output_dir=out,
                    first=5,max_n=6,attempts=1,iterations=5,
                    deep_generations=0)


if __name__=="__main__":
    unittest.main()
