"""Deep packing optimizer: safety, persistence, resume and variation tests."""
import tempfile
import unittest
from pathlib import Path

import numpy as np

from scripts.kaggle_best_registry import initialize_registry,read_registry
from scripts.run_deep_elastic import _mutate,optimize


class DeepElasticTests(unittest.TestCase):
    def test_all_mutation_families_have_valid_shape_and_rotation_range(self):
        base=np.array([[.5,.5,0.],[1.5,.5,.0],[.5,1.5,0.],
                       [1.5,1.5,.0],[2.5,2.5,.0]])
        for mode in range(5):
            output=_mutate(base,np.random.default_rng(33),.08,mode=mode)
            self.assertEqual(output.shape,base.shape)
            self.assertTrue(np.all(np.isfinite(output)))
            self.assertTrue(np.all(np.abs(output[:,2])<=np.pi/4+1e-12))
        np.testing.assert_allclose(base[:,0],[.5,1.5,.5,1.5,2.5])

    def test_read_only_run_writes_progress_without_bank_updates(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            bank=folder/"bank.json"
            initialize_registry(bank)
            before=read_registry(bank)["total_score"]
            output=folder/"pilot"
            result=optimize(registry=bank,n=5,generations=4,
                            iterations=12,seed=45,log_every=2,
                            output_dir=output)
            self.assertEqual(read_registry(bank)["total_score"],before)
            self.assertTrue((output/"progress.json").exists())
            self.assertTrue((output/"best_valid.json").exists())
            self.assertEqual(result["registry_updates"],0)

    def test_resume_rechecks_valid_checkpoint_without_modifying_original(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            bank=folder/"bank.json"
            initialize_registry(bank)
            a=folder/"run_a"
            optimize(registry=bank,n=5,generations=2,
                     iterations=8,seed=7,log_every=1,output_dir=a)
            b=folder/"run_b"
            optimize(registry=bank,n=5,generations=2,
                     iterations=8,seed=8,log_every=1,output_dir=b,resume_dir=a)
            self.assertTrue((a/"best_valid.json").is_file())
            self.assertTrue((b/"best_valid.json").is_file())

    def test_do_not_overwrite_experiments(self):
        with tempfile.TemporaryDirectory() as temp:
            bank=Path(temp)/"bank.json"
            initialize_registry(bank)
            out=Path(temp)/"existing"
            out.mkdir()
            with self.assertRaises(FileExistsError):
                optimize(registry=bank,n=5,generations=1,
                         iterations=1,output_dir=out)


if __name__=="__main__":
    unittest.main()
