import json
import tempfile
import unittest
from pathlib import Path

from gerit.config import RunConfig, SelectionGroup, load_config


class ConfigTests(unittest.TestCase):
    def test_default_split(self):
        self.assertEqual(RunConfig().selection_slots(), {"fitness": 15, "diversity": 5})

    def test_independent_population_counts(self):
        cfg = RunConfig(initial_population=20, next_generation_population=30, offspring_per_parent=3)
        self.assertEqual(cfg.selection_slots(), {"fitness": 23, "diversity": 7})
        self.assertEqual(cfg.initial_population * cfg.offspring_per_parent, 60)

    def test_alternative_split(self):
        cfg = RunConfig(next_generation_population=40, selection_groups=(
            SelectionGroup("fitness", .5), SelectionGroup("diversity", .5)))
        self.assertEqual(cfg.selection_slots(), {"fitness": 20, "diversity": 20})

    def test_invalid_share(self):
        with self.assertRaises(ValueError):
            RunConfig(selection_groups=(SelectionGroup("fitness", .8), SelectionGroup("diversity", .3)))

    def test_unimplemented_group_fails_loudly(self):
        with self.assertRaises(ValueError):
            SelectionGroup("novelty", .25)

    def test_external_input_requires_path(self):
        with self.assertRaises(ValueError):
            RunConfig(initialization_source="file")

    def test_load_example(self):
        cfg = load_config("configs/five-squares.json")
        self.assertEqual(cfg.n_squares, 5)
        self.assertEqual(cfg.selection_slots(), {"fitness": 15, "diversity": 5})


if __name__ == "__main__":
    unittest.main()
