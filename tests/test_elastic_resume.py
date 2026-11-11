"""Checkpoint-resume safety and diagnostics tests."""
import tempfile
import unittest
from pathlib import Path

import numpy as np

from scripts.kaggle_best_registry import initialize_registry,read_registry
from scripts.run_elastic_resume import _load_checkpoint,_perturb,run


class ResumeTests(unittest.TestCase):
    def test_reject_wrong_n(self):
        with tempfile.TemporaryDirectory() as temp:
            f=Path(temp)/"checkpoint.npz"
            np.savez_compressed(f,poses=np.zeros((4,3)),target_n=np.array(4),
                                side_cap=np.array(2.99))
            with self.assertRaises(ValueError):
                _load_checkpoint(f,5)

    def test_perturb_is_reproducible_and_keeps_shape(self):
        pose=np.array([[.5,.5,0.],[1.5,.5,0.],[.5,1.5,0.],
                       [1.5,1.5,0.],[1.,1.,.2]])
        d={"worst_pairs":[(0,4,.4)],"outside_squares":0}
        a=_perturb(pose,d,np.random.default_rng(37),.02,2)
        b=_perturb(pose,d,np.random.default_rng(37),.02,2)
        np.testing.assert_allclose(a,b)
        self.assertEqual(a.shape,(5,3))
        self.assertFalse(np.shares_memory(a,pose))

    def test_dry_run_preserves_archive_and_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            bank=folder/"bank.json"
            initialize_registry(bank)
            poses=np.array([[.5,.5,0],[1.5,.5,0],[.5,1.5,0],
                            [1.5,1.5,0],[1.,1.,.785398163]])
            original=folder/"source.npz"
            np.savez_compressed(original,poses=poses,side_cap=np.array(2.99),
                                target_n=np.array(5),source_n=np.array(4))
            initial=read_registry(bank)["total_score"]
            result=run(registry=bank,checkpoint=original,n=5,attempts=1,
                       iterations=5,report=folder/"report.json",
                       output_checkpoint=folder/"new.npz")
            self.assertEqual(read_registry(bank)["total_score"],initial)
            self.assertFalse(result["applied"])
            self.assertTrue(original.is_file())
            self.assertTrue((folder/"new.npz").is_file())

    def test_output_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/"report.json"
            out.write_text("old")
            with self.assertRaises(FileExistsError):
                run(registry="not-read",checkpoint="not-read",report=out,
                    output_checkpoint=Path(temp)/"new.npz")
            self.assertEqual(out.read_text(),"old")


if __name__=="__main__":
    unittest.main()
