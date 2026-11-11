"""Source-file growth and certified fixed-N deep compression integration."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.kaggle_best_registry import initialize_registry,read_registry
from scripts.run_elastic_repair import run as grow
from scripts.run_deep_elastic import optimize


class N231PipelineTests(unittest.TestCase):
    def test_external_source_and_safe_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)
            bank=d/"bank.json"
            initialize_registry(bank)
            source=d/"n5.json"
            source.write_text(json.dumps(read_registry(bank)["problems"]["5"]))
            before=read_registry(bank)["total_score"]
            result=grow(bank,n=6,attempts=1,iterations=10,
                        seed=5,source_file=source,
                        report=d/"grow.json",checkpoint=d/"near.npz",
                        best_file=d/"best6.json")
            self.assertEqual(result["source_n"],5)
            self.assertEqual(read_registry(bank)["total_score"],before)
            self.assertTrue(source.exists())
            self.assertTrue((d/"grow.json").exists())

    def test_invalid_external_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)
            bank=d/"bank.json"
            initialize_registry(bank)
            source=d/"wrong.json"
            source.write_text(json.dumps(read_registry(bank)["problems"]["4"]))
            with self.assertRaises(ValueError):
                grow(bank,n=6,attempts=1,iterations=5,
                     source_file=source,report=d/"report.json")

    def test_deep_accepts_previously_validated_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)
            bank=d/"bank.json"
            initialize_registry(bank)
            saved=d/"five.json"
            saved.write_text(json.dumps(read_registry(bank)["problems"]["5"]))
            result=optimize(registry=bank,n=5,generations=2,iterations=8,
                            seed=2,log_every=1,output_dir=d/"deep",
                            candidate_file=saved)
            self.assertEqual(result["registry_updates"],0)
            self.assertTrue((d/"deep"/"best_valid.json").exists())

    def test_deep_rejects_mismatched_n(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)
            bank=d/"bank.json"
            initialize_registry(bank)
            saved=d/"four.json"
            saved.write_text(json.dumps(read_registry(bank)["problems"]["4"]))
            with self.assertRaises(ValueError):
                optimize(registry=bank,n=5,generations=1,iterations=5,
                         output_dir=d/"deep",candidate_file=saved)
            self.assertFalse((d/"deep").exists())


if __name__=="__main__":
    unittest.main()
