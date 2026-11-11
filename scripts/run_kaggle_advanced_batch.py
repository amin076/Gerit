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
from gerit.geometry import Packing, Square, grid_baseline, minimum_bounding_square, validate_packing
from gerit.symmetry_operators import multi_parent_quadrant_crossover, geometry_seed_bank
from gerit.evolution import packing_distance
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



def expanded_founder(packing, extra_side):
    """Expand centers while retaining every orientation and original structure.

    A controlled exploratory release: original unit-square sizes do not change.
    It is deliberately not a claim that this makes a better packing.
    """
    if not math.isfinite(extra_side) or extra_side < 0:
        raise ValueError("extra_side must be finite and nonnegative")
    if extra_side == 0:
        return packing
    if not validate_packing(packing, tolerance=0.0).valid:
        raise ValueError("Cannot expand invalid geometry")
    n = len(packing.squares)
    cx = sum(sq.x for sq in packing.squares) / n
    cy = sum(sq.y for sq in packing.squares) / n
    factor = 1.0 + extra_side / max(1.0, packing.container_side - 1.0)
    expanded = minimum_bounding_square(tuple(
        Square(cx + (sq.x - cx) * factor,
               cy + (sq.y - cy) * factor, sq.angle)
        for sq in packing.squares))
    if not validate_packing(expanded, tolerance=0.0).valid:
        raise ValueError("Unexpected invalid released founder")
    if expanded.container_side <= packing.container_side:
        raise ValueError("Released founder failed to expand")
    return expanded


def released_rotation_founder(first, seed):
    """Make a valid rotated exploratory parent by releasing an existing layout."""
    rng = random.Random(seed)
    n = len(first.squares)
    k = math.isqrt(n - 1) + 1
    gap = min(0.18, 0.6 / max(1, k - 1))
    cx = sum(sq.x for sq in first.squares) / n
    cy = sum(sq.y for sq in first.squares) / n
    for factor in (1 + gap, 1 + gap * 1.35, 1 + gap * 1.75):
        for _ in range(8):
            poses = tuple(Square(
                cx + (sq.x - cx) * factor,
                cy + (sq.y - cy) * factor,
                sq.angle + rng.uniform(-gap * 0.30, gap * 0.30),
            ) for sq in first.squares)
            rotated = minimum_bounding_square(poses)
            if (rotated.container_side <= max(grid_baseline(n).container_side,
                                              first.container_side) + 0.75
                    and validate_packing(rotated, tolerance=0.0).valid
                    and any(abs(math.sin(2 * sq.angle)) > 1e-6
                            for sq in rotated.squares)):
                return rotated
    return None


def independent_founder(n, first, seed):
    """Choose an existing independent geometry with real structural difference."""
    options = geometry_seed_bank(n, seed, copies=2)
    rotated = released_rotation_founder(first, seed + 7331)
    if rotated is not None:
        options.append(("released_rotations", rotated))
    eligible = []
    for name, packing in options:
        if packing is None or len(packing.squares) != n:
            continue
        if not validate_packing(packing, tolerance=0.0).valid:
            continue
        distance = packing_distance(first, packing)
        if distance > 1e-7:
            rotated_count = sum(abs(math.sin(2 * sq.angle)) > 1e-6
                                for sq in packing.squares)
            eligible.append((rotated_count > 0, rotated_count,
                             -packing.container_side, distance, name, packing))
    if not eligible:
        return None, None
    *_, name, packing = max(eligible)
    return name, packing

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
    raw_fresh = fresh_founder(n, args.founder, rng)
    fresh = (expanded_founder(raw_fresh, args.initial_release)
             if args.start == "fresh" else raw_fresh)
    archive = from_registry(old) if args.start in ("stored", "mixed") else None
    secondary_founder = None
    if args.start == "stored":
        initial, other = archive, ()
    elif args.start == "mixed":
        initial, other = fresh, (archive,)
    else:
        initial, other = fresh, ()
    if args.start == "fresh" and args.parents >= 2 and args.diverse_founders:
        secondary_founder, second = independent_founder(n, raw_fresh, args.seed + n + 100000)
        if second is not None:
            other = (expanded_founder(second, args.initial_release),)
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
    if args.initial_release:
        run_id += f"-release{args.initial_release:g}"
    run_dir = Path(args.output_root) / run_id
    if run_dir.exists():
        raise FileExistsError(f"Refusing to overwrite history: {run_dir}")
    run_dir.mkdir(parents=True)
    start = time.perf_counter()
    accepted_updates = []

    def archive_new_best(packing, generation):
        candidate = {"n": n, "side": packing.container_side,
                     "squares": [asdict(sq) for sq in packing.squares]}
        outcome = propose_improvement(
            args.registry, candidate, source="gerit_advanced_evolution",
            experiment_id=run_id, generation=generation,
            operator="existing_advanced_structural")
        if outcome["accepted"]:
            accepted_updates.append(outcome)
            print(f"NEW REGISTRY BEST N={n} GEN={generation} "
                  f"L={packing.container_side:.12f} "
                  f"total_score={outcome['total_score']:.12f}", flush=True)

    def progress(g):
        if g.generation == 0 or g.generation % args.report_every == 0 or g.generation == args.generations:
            print(f"N={n} GEN={g.generation}/{args.generations} "
                  f"best_L={g.best_side:.12f} evaluations={g.evaluations} "
                  f"valid_children={g.valid_children} historical_jumps={g.historical_jumps} "
                  f"rotated_parents={g.rotated_parents}/{args.parents} "
                  f"rotated_valid_children={g.rotated_valid_children} "
                  f"elapsed={time.perf_counter()-start:.1f}s", flush=True)

    print(f"START N={n} initial={initial.container_side:.12f} "
          f"stored={old['side']:.12f} mode={args.start} founder={args.founder} "
          f"secondary_founder={secondary_founder} initial_release={args.initial_release:g}", flush=True)
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
        best_callback=archive_new_best,
    )
    poses = tuple((repr(s.x), repr(s.y), repr(s.angle)) for s in result.best.squares)
    check = interval_validate(Candidate(n, poses, "gerit-advanced-evolution", result.best.container_side))
    if not check.valid:
        raise ValueError(f"N={n} independent interval validation failed: {check.reason}")
    # Every new engine record has already been offered during evolution.
    # The final result is rechecked; a previously archived winner is retained.
    archive_new_best(result.best, len(result.history)-1)
    final_score = read_registry(args.registry)["total_score"]
    summary = {
        "n": n, "run_id": run_id, "start_mode": args.start,
        "founder": args.founder, "secondary_founder": secondary_founder,
        "initial_release": args.initial_release,
        "started_from_registry": args.start != "fresh",
        "old_registry_side": old["side"], "best_side": result.best.container_side,
        "interval_validation": check.reason,
        "evaluations": result.evaluations, "generations": len(result.history)-1,
        "accepted_registry_updates": accepted_updates,
        "final_total_score": final_score, "elapsed_seconds": time.perf_counter()-start,
    }
    (run_dir / "kaggle_bank_update.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    print(f"DONE N={n} best_L={result.best.container_side:.12f} "
          f"accepted_improvements={len(accepted_updates)} total_score={final_score:.12f}", flush=True)
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
    p.add_argument("--diverse-founders", action=argparse.BooleanOptionalAction,
                   default=True, help="Seed a second independent geometry when starting fresh")
    p.add_argument("--seed", type=int, default=20261111)
    p.add_argument("--report-every", type=int, default=10)
    p.add_argument("--image-every", type=int, default=50)
    p.add_argument("--exploration-extra", type=float, default=0.8)
    p.add_argument("--initial-release", type=float, default=0.0,
                   help="Additional starting-side space for fresh founders; 0 preserves existing behavior")
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
            or not math.isfinite(a.initial_release) or a.initial_release < 0
            or (a.initial_release > 0 and a.start != "fresh")
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
