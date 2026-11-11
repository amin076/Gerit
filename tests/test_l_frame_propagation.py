"""L-frame regression checks for geometrical propagation and provenance."""
import math
import tempfile
import unittest
from pathlib import Path

from gerit.four_corner_center_45 import four_corner_center_45
from gerit.geometry import validate_packing, grid_baseline
from gerit.kaggle import Candidate, validate as interval_validate
from gerit.l_frame_geometry import l_frame_extend, l_frame_target, SPECIAL_30
from scripts.kaggle_best_registry import initialize_registry, read_registry, propose_improvement
from scripts.run_l_frame_propagation import propagate


class LFrameTests(unittest.TestCase):
    def test_thirty_special_target_counts(self):
        self.assertEqual(len(SPECIAL_30),30)
        self.assertEqual(SPECIAL_30[0],5)
        self.assertEqual(SPECIAL_30[-1],962)
        self.assertEqual(l_frame_target(5,2.707107),10)
        self.assertEqual(l_frame_target(10,3.707107),17)
        self.assertEqual(l_frame_target(17,4.707107),26)

    def test_two_steps_preserve_angles_and_validate(self):
        source=four_corner_center_45(5)
        ten=l_frame_extend(source)
        seventeen=l_frame_extend(ten)
        for n,packing in [(10,ten),(17,seventeen)]:
            with self.subTest(n=n):
                self.assertEqual(len(packing.squares),n)
                self.assertTrue(validate_packing(packing,tolerance=0).valid)
                self.assertTrue(any(abs(s.angle-math.pi/4)<1e-12 for s in packing.squares))
                c=Candidate(n,tuple((repr(s.x),repr(s.y),repr(s.angle))
                                    for s in packing.squares),
                            "unit-test",packing.container_side)
                self.assertTrue(interval_validate(c).valid)
                self.assertLess(packing.container_side,grid_baseline(n).container_side)

    def test_dry_run_keeps_bank_and_cascades(self):
        from dataclasses import asdict
        with tempfile.TemporaryDirectory() as folder:
            bankpath=Path(folder)/"bank.json"
            initialize_registry(bankpath)
            p=four_corner_center_45(5)
            accepted=propose_improvement(
                bankpath,{"n":5,"side":p.container_side,
                          "squares":[asdict(s) for s in p.squares]},
                source="test-five",experiment_id="five-seed",
                generation=0,operator="center45")
            self.assertTrue(accepted["accepted"])
            before=read_registry(bankpath)["total_score"]
            result=propagate(bankpath,max_n=40,apply=False,
                             report=Path(folder)/"dryrun.json",ledger=None)
            self.assertTrue({10,17,26,37}.issubset(set(result["improved_target_counts"])))
            self.assertEqual(read_registry(bankpath)["total_score"],before)
            self.assertLess(result["final_score"],before)

    def test_report_cannot_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            bankpath=Path(folder)/"bank.json"
            initialize_registry(bankpath)
            report=Path(folder)/"report.json"
            report.write_text("archive")
            with self.assertRaises(FileExistsError):
                propagate(bankpath,apply=True,report=report,ledger=None)
            self.assertEqual(report.read_text(),"archive")


if __name__=="__main__":
    unittest.main()
