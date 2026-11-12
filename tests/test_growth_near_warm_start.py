"""Test N-1 growth near-state provenance, warm start and validation."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from scripts.run_deep_elastic import optimize


class GrowthWarmStartTests(unittest.TestCase):
    def test_wrong_founder_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            near=path/"near.npz"
            np.savez_compressed(near,poses=np.zeros((3,3)),
                                side_cap=2.2,source_n=1,target_n=3)
            from gerit.geometry import Packing,Square
            from scripts.run_deep_elastic import _packing_record
            # Any valid 3-square bank packing suffices; avoids writing a
            # real bank and expensive 500-generation optimization.
            record=_packing_record(Packing(tuple(
                Square(.5+i,.5,0) for i in range(3)),3.0))
            with patch("scripts.run_deep_elastic.read_registry",
                       return_value={"problems":{"3":record},
                                     "total_score":28.0}):
                with self.assertRaisesRegex(ValueError,"not N-1"):
                    optimize(registry=path/"bank.json",n=3,generations=1,
                             iterations=1,seed=1,output_dir=path/"output",
                             near_seed_file=near)
            self.assertFalse((path/"output").exists())

    def test_valid_n2_to_n3_near_state_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            from gerit.geometry import Packing,Square
            from scripts.run_deep_elastic import _packing_record
            record=_packing_record(Packing(tuple(
                Square(.5+i,.5,0) for i in range(3)),3.0))
            near=path/"near.npz"
            np.savez_compressed(near,
                poses=np.array([[.5,.5,0.],[1.5,.5,0.],[.5,1.5,0.]]),
                side_cap=2.3,source_n=2,target_n=3)
            with patch("scripts.run_deep_elastic.read_registry",
                       return_value={"problems":{"3":record},
                                     "total_score":28.0}):
                # The incumbent is valid, near poses are not certified.
                optimize(registry=path/"bank.json",n=3,generations=1,
                         iterations=1,seed=1,output_dir=path/"output",
                         near_seed_file=near)
            configuration=json.loads((path/"output"/"configuration.json").read_text())
            self.assertEqual(configuration["near_seed_file"],str(near))


if __name__=="__main__":
    unittest.main()
