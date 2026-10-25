"""Verify a Gerit run from its persisted evidence, including PNG count.

Usage: python scripts/verify_run.py results/run-.../
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from gerit.geometry import Packing, Square, validate_packing


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def verify(directory: Path) -> dict:
    summary = json.loads((directory / "run_summary.json").read_text(encoding="utf-8"))
    people = _jsonl(directory / "individuals.jsonl")
    generations = _jsonl(directory / "generations.jsonl")
    selections = _jsonl(directory / "selection.jsonl")
    images = sorted((directory / "generation_images").glob("gen_*.png"))

    assert len(people) == summary["evaluations"], "Missing or excess individual records"
    assert len({p["individual_id"] for p in people}) == len(people), "Duplicated individual ID"
    known = set()
    valid = set()
    for p in people:
        assert all(parent in known for parent in p["parent_ids"]), "Broken or forward lineage"
        known.add(p["individual_id"])
        if p["valid"]:
            valid.add(p["individual_id"])
        else:
            assert p["rejected_reason"], "Rejection without a reason"

    assert summary["evaluations"] == 1 + summary["accepted_children"] + summary["rejected_children"]
    assert len(generations) == summary["completed_generations"] + 1
    assert len(generations) == summary["population_snapshots"] == summary["population_images"]
    assert [g["generation"] for g in generations] == list(range(len(generations)))
    assert [p.name for p in images] == [f"gen_{i:03d}.png" for i in range(len(generations))]
    for g in generations:
        assert all(i in valid for i in g["selected_ids"]), "Invalid or nonexistent survivor"
        assert g["best_individual_id"] in valid, "Invalid best individual"
    assert all(y["best_side"] <= x["best_side"] + 1e-12
               for x, y in zip(generations, generations[1:])), "Best-so-far increased"
    selected_by_gen = {g["generation"]: set(g["selected_ids"]) for g in generations}
    for event in selections:
        assert event["generation"] > 0, "Unexpected selection in generation zero"
        assert event["individual_id"] in known
        assert event["selected"] == (event["individual_id"] in
                                     selected_by_gen[event["generation"]]), "Selection mismatch"

    best = json.loads((directory / "best_result.json").read_text(encoding="utf-8"))["best"]
    packing = Packing(tuple(Square(**s) for s in best["squares"]), best["side"])
    assert validate_packing(packing, tolerance=0.0).valid, "Invalid best packing"
    assert abs(best["side"] - summary["best_side"]) < 1e-10
    assert summary["elapsed_seconds"] > 0
    assert summary["stop_reason"] in ("max_evaluations", "max_generations")

    return {
        "verification": "passed",
        "completed_generations": summary["completed_generations"],
        "population_images": len(images),
        "evaluations": len(people),
        "lineage_records": len(people),
        "selection_events": len(selections),
        "elapsed_seconds": summary["elapsed_seconds"],
        "best_side": summary["best_side"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify a persisted Gerit experiment")
    parser.add_argument("run_directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.run_directory), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
