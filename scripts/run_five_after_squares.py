"""Run 5 cases immediately after each square k^2, k=22..31.

Fifty targeted cases: 485..489, 530..534, 577..581, 626..630,
677..681, 730..734, 785..789, 842..846, 901..905, 962..966.

For each family, reuse the existing certified growth and deep optimizer.
Every family has its own checkpoint. Re-running this launcher resumes
existing family checkpoints and starts missing families; it never edits
the 1000-case registry. For promotion, use promote_auto_sweep.py.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def groups(first_k=22, last_k=31, width=5):
    if not 1 <= first_k <= last_k <= 31:
        raise ValueError("Require 1 <= first-k <= last-k <= 31")
    if not 1 <= width <= 5:
        raise ValueError("Require 1 <= width <= 5")
    return [(k, k * k + 1, k * k + width)
            for k in range(first_k, last_k + 1)]


def run(*, output_root, first_k=22, last_k=31, width=5,
        attempts=30, iterations=500, deep_generations=200,
        deep_iterations=200, seed=20261115, registry=None):
    root = Path(output_root)
    plan = groups(first_k, last_k, width)
    print(f"FIVE_AFTER_SQUARES groups={len(plan)} targets={len(plan)*width} "
          f"deep_generations={deep_generations} apply=False", flush=True)
    for group_index, (k, first, last) in enumerate(plan, start=1):
        target = root / f"k{k:02d}_n{first}_{last}"
        state_file = target / "sweep_state.json"
        if target.exists() and not state_file.is_file():
            raise FileExistsError(
                f"Existing incomplete/unrecognized directory: {target}. "
                "Preserving files; inspect it before retrying.")
        arguments = [
            sys.executable, "-u",
            str(ROOT / "scripts" / "run_auto_family_sweep.py"),
            "--first", str(first), "--max-n", str(last),
            "--attempts", str(attempts), "--iterations", str(iterations),
            "--deep-generations", str(deep_generations),
            "--deep-iterations", str(deep_iterations),
            "--seed", str(seed + k),
            "--output-dir", str(target),
        ]
        if registry is not None:
            arguments += ["--registry", str(registry)]
        if state_file.exists():
            arguments.append("--resume")
        print(f"\nFAMILY {group_index}/{len(plan)} "
              f"k={k} N={first}..{last} "
              f"resume={state_file.exists()}", flush=True)
        subprocess.run(arguments, cwd=ROOT, check=True)
        state = json.loads(state_file.read_text(encoding="utf-8"))
        if state.get("next_index") != width:
            raise RuntimeError(f"Incomplete checkpoint after run: {state_file}")
        improved = sum(1 for row in state["results"] if row["better"])
        print(f"FAMILY_DONE k={k} completed={width} improved={improved} "
              f"projected_score={state.get('projected_score')}", flush=True)
    print(f"ALL_FAMILIES_DONE groups={len(plan)} targets={len(plan)*width}",
          flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-root",
                   default="results/kaggle_auto/five_after_squares_k22_31")
    p.add_argument("--first-k", type=int, default=22)
    p.add_argument("--last-k", type=int, default=31)
    p.add_argument("--width", type=int, default=5)
    p.add_argument("--attempts", type=int, default=30)
    p.add_argument("--iterations", type=int, default=500)
    p.add_argument("--deep-generations", type=int, default=200)
    p.add_argument("--deep-iterations", type=int, default=200)
    p.add_argument("--seed", type=int, default=20261115)
    p.add_argument("--registry", default=None)
    a = p.parse_args()
    run(output_root=a.output_root, first_k=a.first_k, last_k=a.last_k,
        width=a.width, attempts=a.attempts, iterations=a.iterations,
        deep_generations=a.deep_generations,
        deep_iterations=a.deep_iterations,
        seed=a.seed, registry=a.registry)


if __name__ == "__main__":
    main()
