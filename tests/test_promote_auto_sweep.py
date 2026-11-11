"""Audit and promotion tests: no mutation, strict validation, rerun safety."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.kaggle_best_registry import initialize_registry,read_registry
from scripts.promote_auto_sweep import audit


class PromotionTests(unittest.TestCase):
    def _setup(self,root):
        bank=root/"registry.json"
        initialize_registry(bank)
        item=read_registry(bank)["problems"]["5"]
        candidate=root/"winner.json"
        candidate.write_text(json.dumps(item)+"\n",encoding="utf-8")
        sweep=root/"sweep"
        sweep.mkdir()
        state={"next_index":1,"results":[{
            "n":5,"best_side":item["side"],"best_file":str(candidate),
            "better":False
        }]}
        (sweep/"sweep_state.json").write_text(json.dumps(state))
        return bank,sweep,candidate

    def test_audit_does_not_edit_bank(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            bank,sweep,candidate=self._setup(root)
            before=read_registry(bank)["total_score"]
            result=audit(registry=bank,sweep_dir=sweep,
                         report=root/"audit.json")
            self.assertEqual(result["verified_better"],0)
            self.assertEqual(result["registered"],0)
            self.assertEqual(read_registry(bank)["total_score"],before)

    def test_reject_silent_missing_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            bank,sweep,candidate=self._setup(root)
            state=json.loads((sweep/"sweep_state.json").read_text())
            state["results"][0]["best_side"]=1.9
            state["results"][0]["best_file"]=None
            (sweep/"sweep_state.json").write_text(json.dumps(state))
            with self.assertRaises(ValueError):
                audit(registry=bank,sweep_dir=sweep)

    def test_reject_false_packing_without_modifying_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            bank,sweep,candidate=self._setup(root)
            before=read_registry(bank)["total_score"]
            bad=json.loads(candidate.read_text())
            bad["side"]=1.8
            candidate.write_text(json.dumps(bad))
            with self.assertRaises(ValueError):
                audit(registry=bank,sweep_dir=sweep,apply=True)
            self.assertEqual(read_registry(bank)["total_score"],before)

    def test_report_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            bank,sweep,_=self._setup(root)
            report=root/"existing.json"
            report.write_text("old")
            with self.assertRaises(FileExistsError):
                audit(registry=bank,sweep_dir=sweep,report=report)
            self.assertEqual(report.read_text(),"old")


if __name__=="__main__":
    unittest.main()
