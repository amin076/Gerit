"""Fast smoke coverage for the six-hour multi-N marathon scheduler."""
import math
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.run_gerit_marathon import _candidates, _choose, _worker, run


def fake_bank():
    problems = {}
    for n in range(1, 1001):
        side = float(math.isqrt(n))
        if side * side < n:
            side += 1.
        problems[str(n)] = {"side": side}
    score = math.fsum(problems[str(n)]["side"] / math.sqrt(n) - 1
                      for n in range(1, 1001))
    return {"schema_version": 1, "problems": problems, "total_score": score}


class MarathonTests(unittest.TestCase):
    def setUp(self):
        self.bank = fake_bank()
        self.state = {"jobs": [], "best_files": {}}
        self.conf = {"min_n": 2, "max_n": 1000}

    def test_growth_targets_span_hundreds_not_only_970(self):
        growth, deep = _candidates(self.bank, self.state, self.conf)
        self.assertTrue(growth)
        self.assertTrue(deep)
        self.assertEqual({(n - 1) // 100 for _, _, n, _, _ in growth},
                         set(range(10)))
        first = _choose(self.bank, self.state, self.conf)
        self.assertEqual(first[1], "growth")
        self.assertGreater(self.bank["problems"][str(first[0])]["side"],
                           self.bank["problems"][str(first[0]-1)]["side"])

    def test_fixed_n_search_is_scheduled_every_fourth_job(self):
        self.state["jobs"] = [
            {"n": 2, "method": "growth"},
            {"n": 5, "method": "growth"},
            {"n": 10, "method": "growth"},
        ]
        self.assertEqual(_choose(self.bank,self.state,self.conf)[1],"deep")

    def test_worker_streams_to_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"test.log"
            result=_worker([sys.executable,"-u","-c",
                            "print('MARATHON_SMOKE_TEST')"],
                           path,time.monotonic()+10)
            self.assertEqual(result["returncode"],0)
            self.assertFalse(result["timed_out"])
            self.assertIn("MARATHON_SMOKE_TEST",path.read_text())

    def test_short_dry_run_resumes_without_modifying_bank(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/"run"
            bank_path=Path(tmp)/"bank.json"
            import json
            bank_path.write_text(json.dumps(self.bank),encoding="utf-8")
            worker_result={"returncode":0,"timed_out":False}
            with patch("scripts.run_gerit_marathon._worker",
                       return_value=worker_result):
                first=run(registry=bank_path,output_dir=output,hours=.01,
                          max_task_minutes=1,max_tasks=2)
                self.assertEqual(first["tasks_completed"],2)
                self.assertTrue((output/"marathon_state.json").exists())
                continued=run(registry=bank_path,output_dir=output,
                              hours=.01,max_task_minutes=1,
                              max_tasks=3,resume=True)
                self.assertEqual(continued["tasks_completed"],3)
            self.assertEqual(json.loads(bank_path.read_text()),self.bank)


if __name__ == "__main__":
    unittest.main()
