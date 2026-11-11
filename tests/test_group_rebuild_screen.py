"""Bounded group rebuild must preserve strict geometry and archive integrity."""
import tempfile, unittest
from pathlib import Path
from gerit.geometry import Packing,Square,validate_packing
from gerit.group_rebuild_geometry import rebuild_with_extra
from scripts.kaggle_best_registry import initialize_registry,read_registry
from scripts.run_group_rebuild_screen import run

class GroupRebuildTests(unittest.TestCase):
    def test_group_rebuild_returns_only_valid_plus_one(self):
        seed=Packing((Square(.5,.5),Square(2.5,.5),Square(.5,2.5)),3.)
        best,stats=rebuild_with_extra(seed,3.5,seed=17,attempts=8,
                                      group_size=2,probes=10)
        self.assertEqual(stats["attempts"],8)
        if best:
            self.assertEqual(len(best.squares),4)
            self.assertTrue(validate_packing(best,tolerance=0).valid)
            self.assertLess(best.container_side,3.5)

    def test_safe_dry_run(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"bank.json"
            initialize_registry(p)
            before=read_registry(p)["total_score"]
            result=run(p,report=Path(d)/"report.json",ledger=None,summary=None,
                       max_n=20,attempts=2,probes=5,group_size=2)
            self.assertEqual(before,read_registry(p)["total_score"])
            self.assertEqual(before,result["initial_score"])
            self.assertTrue(Path(d,"report.json").exists())

    def test_does_not_clobber_report(self):
        with tempfile.TemporaryDirectory() as d:
            report=Path(d)/"report.json"
            report.write_text("old")
            with self.assertRaises(FileExistsError):
                run("unused",report=report,ledger=None,summary=None)
            self.assertEqual(report.read_text(),"old")

if __name__=="__main__":
    unittest.main()
