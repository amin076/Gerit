"""All fifteen N=4*m*m+1 center 45 geometry regression checks."""
import math
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from gerit.four_corner_center_45 import SPECIAL_COUNTS, four_corner_center_45
from gerit.geometry import grid_baseline, validate_packing
from scripts.run_center45_family import run_family


class Center45FamilyTests(unittest.TestCase):
    def test_exact_15_counts(self):
        self.assertEqual(len(SPECIAL_COUNTS),15)
        self.assertEqual(SPECIAL_COUNTS[0],5)
        self.assertEqual(SPECIAL_COUNTS[-1],901)
        self.assertNotIn(962,SPECIAL_COUNTS)

    def test_valid_corner_geometry_and_center_angle(self):
        for n in (5,17,37,65,145):
            candidate=four_corner_center_45(n)
            self.assertEqual(len(candidate.squares),n)
            self.assertTrue(validate_packing(candidate,tolerance=0).valid,n)
            self.assertAlmostEqual(candidate.squares[-1].angle,math.pi/4,places=12)
            self.assertTrue(all(s.angle == 0 for s in candidate.squares[:-1]))
            self.assertLess(candidate.container_side,grid_baseline(n).container_side)

    def test_largest_proposed_geometry_valid(self):
        candidate=four_corner_center_45(901)
        self.assertEqual(len(candidate.squares),901)
        self.assertTrue(validate_packing(candidate,tolerance=0).valid)
        self.assertLess(candidate.container_side,31)

    def test_invalid_counts_rejected(self):
        for n in (2,6,10,26,1000,1025):
            with self.assertRaises(ValueError):
                four_corner_center_45(n)

    def test_report_dry_run_does_not_update_registry(self):
        import scripts.run_center45_family as runner
        bank={"problems":{"17":{"side":5.0}},
              "total_score":28.0}
        with TemporaryDirectory() as folder:
            dest=Path(folder)/"report.json"
            with patch.object(runner,"read_registry",return_value=bank),patch.object(
                runner,"propose_improvement") as offer:
                result=run_family([17],"unused",report=dest)
            self.assertEqual(result["count"],1)
            self.assertTrue(result["results"][0]["valid"])
            self.assertTrue(result["results"][0]["status"]=="improvement_available")
            offer.assert_not_called()
            self.assertTrue(dest.exists())


if __name__=="__main__":
    unittest.main()
