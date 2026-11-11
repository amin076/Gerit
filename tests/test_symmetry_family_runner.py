"""Six symmetry families, validity, provenance, and registry integration."""
import csv
import json
import math
import random
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from gerit.geometry import validate_packing
from gerit.symmetry_family_search import (
    FAMILIES,initial_family_seed,search_family,_symmetry_move,
)
from scripts.kaggle_method_ledger import record_attempt,summarize_ledger
from scripts.run_symmetry_family import run_one


class SymmetryFamilyTests(unittest.TestCase):
    def test_six_families_and_seed_validity(self):
        self.assertEqual(len(FAMILIES),6)
        for n in (5,8,10,11,17,20):
            for family in FAMILIES:
                with self.subTest(n=n,family=family):
                    p=initial_family_seed(n,family,random.Random(n))
                    self.assertEqual(len(p.squares),n)
                    self.assertTrue(validate_packing(p,tolerance=0).valid)

    def test_search_stays_strictly_valid(self):
        for family in FAMILIES:
            with self.subTest(family=family):
                r=search_family(10,family,seed=909,iterations=20,
                                release=.24,report_every=10)
                self.assertEqual(r.iterations,20)
                self.assertTrue(validate_packing(r.best,tolerance=0).valid)
                self.assertLessEqual(r.best.container_side,r.initial_side+1e-9)

    def test_three_plus_one_allows_asymmetric_move(self):
        r=search_family(17,"three_plus_one",seed=120,iterations=30)
        self.assertTrue(validate_packing(r.best,tolerance=0).valid)

    def test_invalid_family_rejected(self):
        with self.assertRaises(ValueError):
            search_family(10,"missing",seed=2)

    def test_ledger_preserves_method_fields(self):
        with TemporaryDirectory() as folder:
            path=Path(folder)/"ledger.jsonl"
            event=record_attempt(
                path,n=17,family="fourfold",script="scripts/run_fourfold_family.py",
                algorithm="constrained_symmetry_geometry_refinement",
                seed=14,parameters={"iterations":20},before_side=5,
                candidate_side=4.8,valid=True,validation="certified interval SAT",
                accepted=True,experiment_id="ex17",generation=20)
            self.assertEqual(event["family"],"fourfold")
            self.assertEqual(len(event["event_id"]),64)
            data=json.loads(path.read_text().strip())
            self.assertEqual(data["algorithm"],event["algorithm"])
            summary=summarize_ledger(path,Path(folder)/"summary.csv")
            self.assertEqual(summary[0]["accepted"],1)

    def test_runner_dry_run_keeps_registry_unchanged(self):
        bank={"problems":{"17":{"side":5.0}},"total_score":28.0}
        with TemporaryDirectory() as folder:
            log=Path(folder)/"events.jsonl"
            with patch("scripts.run_symmetry_family.read_registry",
                       return_value=bank), patch(
                        "scripts.run_symmetry_family.propose_improvement"
                       ) as offer:
                report=run_one(
                    "fourfold",17,registry="unused",ledger=log,
                    output_dir=folder,seed=188,iterations=10,
                    release=.1,report_every=5,apply=False)
            self.assertTrue(Path(folder,report["experiment_id"]+".json").exists())
            self.assertTrue(log.exists())
            self.assertEqual(report["n"],17)
            offer.assert_not_called()


if __name__=="__main__":
    unittest.main()
