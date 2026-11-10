"""Independent tests for the competition integration."""
import json
import math
import tempfile
import unittest
from pathlib import Path

from gerit.kaggle import (Candidate,baseline_total,grid,grid_side,baseline_score,
                          puzzle_score,validate,scan,export,reimport,score_report)


class KaggleIntegrationTests(unittest.TestCase):
    def test_grid_examples(self):
        for n in (1,2,5,12,17,100,1000):
            with self.subTest(n=n):
                c=grid(n)
                check=validate(c)
                self.assertTrue(check.valid,check.reason)
                self.assertEqual(check.side,grid_side(n))
                self.assertAlmostEqual(puzzle_score(n,check.side),baseline_score(n))

    def test_score(self):
        self.assertEqual(puzzle_score(1,1),0)
        self.assertEqual(puzzle_score(4,2),0)
        self.assertAlmostEqual(puzzle_score(5,3),3/math.sqrt(5)-1)
        self.assertGreater(baseline_total(),0)

    def test_touching_and_overlap(self):
        edge=Candidate(2,(("0.5","0.5","0"),("1.5","0.5","0")),"test")
        corner=Candidate(2,(("0.5","0.5","0"),("1.5","1.5","0")),"test")
        overlap=Candidate(2,(("0.5","0.5","0"),("1.499999999999999","0.5","0")),"test")
        rotated_overlap=Candidate(2,(("0.5","0.5","0"),
                                     ("1.4","0.5","0.7853981633974483")),"test")
        separated=Candidate(2,(("0.5","0.5","0"),
                               ("2.5","0.5","0.7853981633974483")),"test")
        self.assertTrue(validate(edge).valid)
        self.assertTrue(validate(corner).valid)
        self.assertFalse(validate(overlap).valid)
        self.assertFalse(validate(rotated_overlap).valid)
        self.assertTrue(validate(separated).valid)

    def test_reject_invalid_and_fake_side(self):
        self.assertFalse(validate(Candidate(1,(("nan","0","0"),),"test")).valid)
        self.assertFalse(validate(Candidate(1,(("0.5","0.5","0"),),"test",2)).valid)
        self.assertFalse(validate(Candidate(2,(("0.5","0.5","0"),),"test")).valid)

    def test_inventory_and_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/"poses.json").write_text(json.dumps({"best":{"side":2,"squares":[
                {"x":.5,"y":.5,"angle":0},{"x":1.5,"y":.5,"angle":0}]}}))
            (root/"scalar.json").write_text('{"best_side":3.5}')
            found,audit=scan([root])
            self.assertIn(2,found)
            self.assertEqual(len(audit),2)
            self.assertTrue(any("Scalar-only" in x["reason"] for x in audit))
            partial=root/"partial.csv"
            self.assertEqual(export(partial,found,complete=False),2)
            self.assertEqual(len(reimport(partial)),1)
            full=root/"full.csv"
            self.assertEqual(export(full,found,complete=True),500500)
            all_puzzles=reimport(full)
            self.assertEqual(len(all_puzzles),1000)
            self.assertTrue(validate(all_puzzles[1000]).valid)
            self.assertEqual(score_report(found)["improved_N"],0)

    def test_real_archived_round15_if_present(self):
        path=Path("data/round15_selected_population_final.json")
        if not path.is_file():
            self.skipTest("Historical population file not present")
        found,audit=scan([path])
        self.assertEqual(len(audit),20)
        self.assertIn(12,found)
        self.assertTrue(validate(found[12]).valid)


if __name__=="__main__":
    unittest.main()
