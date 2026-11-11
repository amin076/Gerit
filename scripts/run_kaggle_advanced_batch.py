"""Screen multiple square counts with Gerit's EXISTING advanced evolutionary engine.

The 1000-answer registry is an independent output archive, not a mandatory
fitness target or population seed. Modes: fresh, stored, mixed.
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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gerit.config import load_config
from gerit.evolution import evolve
from gerit.geometry import Packing, Square, grid_baseline, validate_packing
from gerit.symmetry_operators import multi_parent_quadrant_crossover
from gerit.kaggle import Candidate, validate as interval_validate
from gerit.contact_compaction import propose_contact_compaction
from gerit.packing_geometry_moves import propose_pivot_release
from gerit.adaptive_v3 import propose_reconfigure
from gerit.contact_relocation import propose_contact_relocate
from scripts.kaggle_best_registry import read_registry, propose_improvement


def from_registry(entry):
    result = Packing(
        tuple(Square(float(v["x"]), float(v["y"]), float(v["angle"]))
              for v in entry["squares"]),
        float(entry["side"]))
    if len(result.squares) != entry["n"] or not validate_packing(result, tolerance=0.0).valid:
        raise ValueError("Invalid stored registry packing")
    return result


def fresh_founder(n, kind, rng):
    """Use original Gerit geometrical founders, never copy a benchmark."""
    if n == 5 and kind in ("auto", "corner-center"):
        # Use the old analytic corner/center geometry (45 degree center).
        # This is a founder, never a restriction on future rotations.
        from experiments.five_squares.optimizer import best_inward_for_angle
        candidate, _ = best_inward_for_angle(math.pi / 4)
        return candidate
    if kind in ("symmetry", "auto"):
        from gerit.symmetry_operators import fourfold_seed, diagonal_pairs_seed, corner_first_seed
        strategies = (fourfold_seed, diagonal_pairs_seed, corner_first_seed)
        candidate = strategies[rng.randrange(len(strategies))](n, rng)
        if candidate is not None:
            return candidate
    return grid_baseline(n)


def structural_move(parent, rng, cap):
    """Existing generic free-rotation, compaction and relocation operators."""
    roll = rng.random()
    if roll < .35:
        return propose_contact_compaction(parent, rng, cap, attempts=24)
    if roll < .67:
        return propose_pivot_release(parent, rng, cap, attempts=36)
    if roll < .84:
        candidate, _ = propose_reconfigure(parent, rng, cap, attempts=24)
    else:
        candidate, _ = propose_contact_relocate(parent, rng, cap, attempts=24)
    return candidate


def run_one(n, args, bank):
    old = bank["problems"][str(n)]
    rng = random.Random(args.seed + n)
    fresh = fresh_founder(n, args.founder, rng)
    archive = from_registry(old) if args.start in ("stored", "mixed") else None
    if args.start == "stored":
        initial, other = archive, ()
    elif args.start == "mixed":
        initial, other = fresh, (archive,)
    else:
        initial, other = fresh, ()
    # Any initial stored champion is optional; no side-length hard cap equals the
    # champion. All valid offspring may explore a larger container.
    side_cap = max(float(grid_baseline(n).container_side),
                   float(initial.container_side),
                   *(float(p.container_side) for p in other))
    exploration_cap = side_cap + args.exploration_extra
    cfg = replace(
        load_config(ROOT / "configs/five-squares.json"),
        n_squares=n, initial_container_side=side_cap,
        initial_population=args.parents, next_generation_population=args.parents,
        offspring_per_parent=args.offspring,
        max_generations=args.generations,
        max_evaluations=args.generations * args.parents * args.offspring + 10000,
        seed=args.seed + n,
    )
    run_id = f"n{n}-g{args.generations}-p{args.parents}-s{args.seed+n}-{args.start}-{args.founder}"
    run_dir = Path(args.output_root) / run_id
    if run_dir.exists():
        raise FileExistsError(f"Refusing to overwrite history: {run_dir}")
    run_dir.mkdir(parents=True)
    start = time.perf_counter()

    def progress(g):
        if g.generation == 0 or g.generation % args.report_every == 0 or g.generation == args.generations:
            print(f"N={n} GEN={g.generation}/{args.generations} "
                  f"best_L={g.best_side:.12f} evaluations={g.evaluations} "
                  f"valid_children={g.valid_children} historical_jumps={g.historical_jumps} "
                  f"rotated_parents={g.rotated_parents}/{args.parents} "
                  f"elapsed={time.perf_counter()-start:.1f}s", flush=True)

    print(f"START N={n} initial={initial.container_side:.12f} "
          f"stored={old['side']:.12f} mode={args.start} founder={args.founder}", flush=True)
    result = evolve(
        cfg, output_dir=str(run_dir), image_every=args.image_every,
        coordinated=True, initial_seed=initial, initial_seeds=other,
        structural_mutator=lambda parent, r: structural_move(parent, r, exploration_cap),
        structural_probability=args.structural_probability,
        multi_parent_mutator=lambda first, second, r: multi_parent_quadrant_crossover(
            first, second, r, exploration_cap),
        multi_parent_probability=args.crossover_probability,
        exploration_side_cap=exploration_cap,
        historical_jump_every=args.historical_jump_every,
        historical_stagnation_after=args.historical_stagnation_after,
        progress_callback=progress,
    )
    poses = tuple((repr(s.x), repr(s.y), repr(s.angle)) for s in result.best.squares)
    check = interval_validate(Candidate(n, poses, "gerit-advanced-evolution", result.best.container_side))
    if not check.valid:
        raise ValueError(f"N={n} independent interval validation failed: {check.reason}")
    candidate = {"n": n, "side": result.best.container_side,
                 "squares": [asdict(s) for s in result.best.squares]}
    # Recheck latest state after preceding runs, so no stale bank replacement.
    update = propose_improvement(args.registry, candidate,
                                 source="gerit_advanced_evolution",
                                 experiment_id=run_id,
                                 generation=len(result.history)-1,
                                 operator="existing_advanced_structural")
    summary = {
        "n": n, "run_id": run_id, "start_mode": args.start,
        "founder": args.founder, "started_from_registry": args.start != "fresh",
        "old_registry_side": old["side"], "best_side": result.best.container_side,
        "interval_validation": check.reason,
        "evaluations": result.evaluations, "generations": len(result.history)-1,
        "registry_update": update, "elapsed_seconds": time.perf_counter()-start,
    }
    (run_dir / "kaggle_bank_update.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    print(f"DONE N={n} best_L={result.best.container_side:.12f} "
          f"accepted={update['accepted']} total_score={update['total_score']:.12f}", flush=True)
    return summary


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--counts", nargs="+", type=int, default=[6, 7, 8, 10])
    p.add_argument("--registry", default="results/kaggle_baseline/best_registry.json")
    p.add_argument("--start", choices=("fresh", "stored", "mixed"), default="fresh",
                   help="Registry is archival by default and NOT a mandatory founder")
    p.add_argument("--founder", choices=("auto", "corner-center", "symmetry"),
                   default="auto")
    p.add_argument("--generations", type=int, default=50)
    p.add_argument("--parents", type=int, default=2)
    p.add_argument("--offspring", type=int, default=5)
    p.add_argument("--seed", type=int, default=20261111)
    p.add_argument("--report-every", type=int, default=10)
    p.add_argument("--image-every", type=int, default=50)
    p.add_argument("--exploration-extra", type=float, default=0.8)
    p.add_argument("--structural-probability", type=float, default=0.35)
    p.add_argument("--crossover-probability", type=float, default=0.20)
    p.add_argument("--historical-jump-every", type=int, default=20)
    p.add_argument("--historical-stagnation-after", type=int, default=30)
    p.add_argument("--output-root", default="results/kaggle_advanced_runs")
    a = p.parse_args()
    if (not a.counts or len(set(a.counts)) != len(a.counts)
            or any(not 1 <= n <= 1000 for n in a.counts)
            or a.parents < 2 or a.generations < 1 or a.offspring < 1
            or a.report_every < 1 or a.image_every < 1
            or not math.isfinite(a.exploration_extra) or a.exploration_extra < 0
            or not 0 <= a.structural_probability <= 1
            or not 0 <= a.crossover_probability <= 1
            or a.structural_probability + a.crossover_probability > 1
            or a.historical_jump_every < 0 or a.historical_stagnation_after < 1):
        p.error("Invalid experiment parameters")
    bank = read_registry(a.registry)
    for n in a.counts:
        if math.isqrt(n) ** 2 == n:
            print(f"SKIP N={n}: exact grid already area-optimal", flush=True)
            continue
        # Re-read registry before each run to pick up earlier accepted results.
        run_one(n, a, read_registry(a.registry))
    print("BATCH FINISHED", flush=True)


if __name__ == "__main__":
    main()
