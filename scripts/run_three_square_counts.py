"""Sequential 500-generation N=17,18,19 experiments using the unchanged Gerit engine.

Each puzzle starts from a constructive grid, not a catalogued record.
This is a baseline experiment; comparison references are only for reporting.
No five-square fixed-center or answer-injection operator is used.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gerit.config import load_config
from gerit.evolution import evolve
from gerit.geometry import grid_baseline, validate_packing
from gerit.kaggle import Candidate, puzzle_score, validate
from gerit.contact_compaction import propose_contact_compaction
from gerit.packing_geometry_moves import propose_pivot_release
from gerit.contact_relocation import propose_contact_relocate
from gerit.adaptive_v3 import propose_reconfigure

DEFAULT_COUNTS = (17, 18, 19)
# Reference-only, NEVER used to initialize or mutate candidates.
PUBLISHED_REFERENCE_L = {
    17: 4.67553009360455,
    18: 4.82287565553229,
    19: 4.88561808316412,
}


def geometry_only_mutation(parent, rng: random.Random, side_cap: float,
                           contact_probability: float = 0.35):
    """Generic geometric proposals; no baked-in optimal N or angle."""
    if rng.random() < contact_probability:
        return propose_contact_compaction(
            parent, rng, side_cap, attempts=40,
            scales=(0.045, 0.009, 0.0015))
    choice = rng.random()
    if choice < 0.55:
        return propose_pivot_release(parent, rng, side_cap, attempts=72)
    if choice < 0.78:
        candidate, _ = propose_reconfigure(parent, rng, side_cap, attempts=30)
    else:
        candidate, _ = propose_contact_relocate(parent, rng, side_cap, attempts=30)
    return candidate


def run_one(n: int, a, out_dir: Path) -> dict:
    initial = grid_baseline(n)
    assert validate_packing(initial, tolerance=0.0).valid
    side_cap = initial.container_side + a.exploration_extra_side
    seed = a.seed + n  # distinct deterministic RNG streams for each N
    cfg = replace(
        load_config(ROOT / "configs" / "five-squares.json"),
        n_squares=n,
        initial_container_side=initial.container_side,
        initial_population=a.parents,
        next_generation_population=a.parents,
        offspring_per_parent=a.offspring_per_parent,
        max_generations=a.generations,
        max_evaluations=a.generations * a.parents * a.offspring_per_parent + 10000,
        seed=seed,
    )
    started = time.perf_counter()
    print(f"\n{'=' * 68}\nSTART N={n} | seed={seed} | initial L={initial.container_side:.9f} | "
          f"reference L={PUBLISHED_REFERENCE_L[n]:.9f} | generations={a.generations}",
          flush=True)

    def report(g):
        if g.generation == 0 or g.generation % a.report_every == 0 or g.generation == a.generations:
            print(
                f"N={n:2d} GEN {g.generation:4d}/{a.generations} | "
                f"best_L={g.best_side:.12f} | score={puzzle_score(n,g.best_side):.9f} | "
                f"valid_children={g.valid_children} | diversity={g.geometric_distinct}/{a.parents} | "
                f"historical_jumps={g.historical_jumps} | "
                f"elapsed={time.perf_counter()-started:.1f}s",
                flush=True,
            )

    result = evolve(
        cfg,
        output_dir=str(out_dir),
        image_columns=4,
        coordinated=True,
        initial_seed=initial,
        structural_mutator=lambda parent, rng: geometry_only_mutation(
            parent, rng, side_cap, a.contact_probability),
        structural_probability=a.structural_probability,
        exploration_side_cap=side_cap,
        image_every=a.image_every,
        progress_callback=report,
        historical_jump_every=a.historical_jump_every,
        historical_stagnation_after=a.historical_stagnation_after,
    )
    poses = tuple((repr(s.x), repr(s.y), repr(s.angle)) for s in result.best.squares)
    check = validate(Candidate(n, poses, "Gerit N17/18/19 evolutionary search",
                               result.best.container_side))
    if not check.valid:
        raise RuntimeError(f"N={n}: independent interval validator failed: {check.reason}")
    summary = {
        "n": n,
        "seed": seed,
        "generations": len(result.history)-1,
        "parents": a.parents,
        "offspring_per_parent": a.offspring_per_parent,
        "initial_L": initial.container_side,
        "best_L": check.side,
        "improvement": initial.container_side - check.side,
        "score": puzzle_score(n, check.side),
        "published_reference_L": PUBLISHED_REFERENCE_L[n],
        "gap_to_published_reference": check.side - PUBLISHED_REFERENCE_L[n],
        "reference_not_used_for_search": True,
        "validation": check.reason,
        "evaluations": result.evaluations,
        "accepted_children": result.accepted_children,
        "elapsed_seconds": time.perf_counter()-started,
        "best_squares": [asdict(s) for s in result.best.squares],
    }
    (out_dir / "experiment_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (out_dir / "best_packing.json").write_text(
        json.dumps({"side": check.side, "squares": summary["best_squares"]}, indent=2) + "\n",
        encoding="utf-8")
    print(f"COMPLETE N={n} | best_L={check.side:.12f} | "
          f"published_reference_L={PUBLISHED_REFERENCE_L[n]:.12f} | "
          f"gap={summary['gap_to_published_reference']:+.9f} | "
          f"validation={check.reason}", flush=True)
    return {k: v for k, v in summary.items() if k != "best_squares"}


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Run N=17,18,19 sequentially, each with 500 real generations.")
    p.add_argument("--counts", nargs="+", type=int, default=list(DEFAULT_COUNTS),
                   choices=DEFAULT_COUNTS)
    p.add_argument("--generations", type=int, default=500)
    p.add_argument("--parents", type=int, default=20)
    p.add_argument("--offspring-per-parent", type=int, default=5)
    p.add_argument("--seed", type=int, default=2715)
    p.add_argument("--report-every", type=int, default=20)
    p.add_argument("--image-every", type=int, default=100)
    p.add_argument("--exploration-extra-side", type=float, default=0.8)
    p.add_argument("--structural-probability", type=float, default=0.35)
    p.add_argument("--contact-probability", type=float, default=0.35)
    p.add_argument("--historical-jump-every", type=int, default=20)
    p.add_argument("--historical-stagnation-after", type=int, default=30)
    p.add_argument("--out-root", type=Path, default=Path("results/n17-n18-n19-500"))
    a = p.parse_args(argv)
    if len(set(a.counts)) != len(a.counts):
        p.error("Duplicate N in --counts")
    if a.generations < 1 or a.parents < 2 or a.offspring_per_parent < 1:
        p.error("generations>=1, parents>=2 and offspring-per-parent>=1 required")
    if a.report_every < 1 or a.image_every < 1:
        p.error("report-every and image-every must be positive")
    if not math.isfinite(a.exploration_extra_side) or a.exploration_extra_side < 0:
        p.error("exploration-extra-side must be finite and nonnegative")
    if not (0 <= a.structural_probability <= 1 and 0 <= a.contact_probability <= 1):
        p.error("probabilities must be between 0 and 1")
    if a.historical_jump_every < 0 or a.historical_stagnation_after < 1:
        p.error("historical settings invalid")
    if a.out_root.exists():
        p.error(f"Output already exists; choose another --out-root: {a.out_root}")

    a.out_root.mkdir(parents=True)
    summary = []
    try:
        for n in a.counts:
            output = a.out_root / f"n{n}"
            output.mkdir()
            item = run_one(n, a, output)
            summary.append(item)
            (a.out_root / "sequential_summary.json").write_text(
                json.dumps({"requested_counts": a.counts, "completed": summary,
                            "status": "in_progress"}, indent=2) + "\n",
                encoding="utf-8")
    except Exception as exc:
        (a.out_root / "sequential_summary.json").write_text(
            json.dumps({"requested_counts": a.counts, "completed": summary,
                        "status": "failed", "error": repr(exc)}, indent=2) + "\n",
            encoding="utf-8")
        raise
    (a.out_root / "sequential_summary.json").write_text(
        json.dumps({"requested_counts": a.counts, "completed": summary,
                    "status": "completed"}, indent=2) + "\n", encoding="utf-8")
    print("\nALL REQUESTED PUZZLES COMPLETED\n" +
          "\n".join(f"N={x['n']} best={x['best_L']:.12f} "
                    f"reference={x['published_reference_L']:.12f}" for x in summary),
          flush=True)


if __name__ == "__main__":
    main()
