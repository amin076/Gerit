"""Run a small Gerit screening experiment and offer its best result to the registry.

Uses the EXISTING gerit.evolution.evolve engine; this is NOT the advanced
historical-branching engine. Start with low N and a small evaluation budget.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import asdict
from pathlib import Path

from gerit.config import RunConfig, SelectionGroup
from gerit.evolution import evolve
from scripts.kaggle_best_registry import propose_improvement, read_registry


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="results/kaggle_baseline/best_registry.json")
    parser.add_argument("--n", type=int, default=5)
    parser.add_argument("--generations", type=int, default=50)
    parser.add_argument("--parents", type=int, default=2)
    parser.add_argument("--offspring", type=int, default=5)
    parser.add_argument("--seed", type=int, default=20261111)
    parser.add_argument("--report-every", type=int, default=10)
    parser.add_argument("--experiment-id", default=None)
    parser.add_argument("--mode", choices=("basic", "learning", "coordinated"),
                        default="coordinated")
    parser.add_argument("--results-dir", default="results/kaggle_screening")
    args = parser.parse_args()
    if not (1 <= args.n <= 1000 and args.parents >= 2
            and args.generations > 0 and args.offspring > 0 and args.report_every > 0):
        parser.error("Invalid n / parents / generations / offspring / report-every")
    bank = read_registry(args.registry)
    current = bank["problems"][str(args.n)]
    side_cap = math.ceil(math.sqrt(args.n))
    experiment_id = args.experiment_id or (
        f"n{args.n}-g{args.generations}-p{args.parents}-s{args.seed}-{args.mode}")
    result_file = Path(args.results_dir) / (experiment_id + ".json")
    if result_file.exists():
        raise FileExistsError(f"Experiment exists: {result_file}")
    cfg = RunConfig(
        n_squares=args.n, initial_population=args.parents,
        next_generation_population=args.parents,
        offspring_per_parent=args.offspring,
        selection_groups=(SelectionGroup("fitness", 0.5),
                          SelectionGroup("diversity", 0.5)),
        initialization_source="grid_mutations",
        max_generations=args.generations,
        max_evaluations=max(100, args.parents * args.offspring * (args.generations+2)),
        seed=args.seed, initial_container_side=float(side_cap))
    started = time.perf_counter()

    def on_progress(gen):
        if gen.generation % args.report_every == 0 or gen.generation == args.generations:
            print(f"GEN {gen.generation}/{args.generations} "
                  f"best_L={gen.best_side:.12f} "
                  f"valid_children={gen.valid_children} "
                  f"evaluations={gen.evaluations} "
                  f"elapsed={time.perf_counter()-started:.1f}s", flush=True)

    print(f"START n={args.n} generations={args.generations} "
          f"parents={args.parents} mode={args.mode} "
          f"stored_best={current['side']:.12f}", flush=True)
    result = evolve(cfg, coordinated=args.mode == "coordinated",
                    learning=args.mode == "learning",
                    progress_callback=on_progress)
    candidate = {
        "n": args.n, "side": result.best.container_side,
        "squares": [asdict(square) for square in result.best.squares]
    }
    acceptance = propose_improvement(
        args.registry, candidate, source="gerit",
        experiment_id=experiment_id, generation=len(result.history)-1,
        operator=args.mode)
    result_file.parent.mkdir(parents=True, exist_ok=True)
    # Store the complete small experiment outcome, preserving provenance.
    result_file.write_text(json.dumps({
        "experiment_id": experiment_id,
        "requested": vars(args),
        "initial_registry_best_side": current["side"],
        "experiment": result.to_dict(),
        "registry_update": acceptance,
        "elapsed_seconds": time.perf_counter() - started,
    }, indent=2), encoding="utf-8")
    print(f"FINISHED best_L={result.best.container_side:.12f} "
          f"accepted={acceptance['accepted']} "
          f"total_score={acceptance['total_score']:.12f} "
          f"saved={result_file}", flush=True)


if __name__ == "__main__":
    main()
