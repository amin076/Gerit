"""Real Gerit generations from the user's five-square corner-center seed.

Uses gerit.evolution.evolve's actual parent selection, offspring, lineage,
generation snapshots and normal coordinated mutation alongside an optional
specialist structural mutation. No pre-optimized geometry is ever injected.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import time
import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from experiments.five_squares.optimizer import corner_center_seed, best_inward_for_angle
from gerit.config import load_config
from gerit.evolution import evolve
from gerit.geometry import Packing, validate_packing
from gerit.kaggle import Candidate, validate, puzzle_score, baseline_score
from gerit.adaptive_v3 import propose_reconfigure
from gerit.contact_relocation import propose_contact_relocate


def corner_center_mutation(parent: Packing, rng: random.Random) -> Packing | None:
    """Coordinated operator inside Gerit's evolutionary offspring loop."""
    if len(parent.squares) != 5:
        return None
    current_angle=abs(parent.squares[4].angle) % (math.pi/2)
    current_angle=min(current_angle,math.pi/2-current_angle)
    if rng.random() < 0.22:
        angle=rng.uniform(0,math.pi/4)
    else:
        angle=min(math.pi/4,max(0.0,current_angle+rng.gauss(0.0,0.12)))
    candidate,_=best_inward_for_angle(angle)
    return candidate


def free_structure_mutation(parent: Packing, rng: random.Random, side_cap: float) -> Packing | None:
    """Historical Gerit structural jump: relocate ANY 1-3 squares and rotate freely.

    Unlike the old specialist five-square operator, this does NOT rebuild
    corners at angle zero and has no special preference for square index 4.
    """
    if rng.random() < 0.5:
        result,_ = propose_reconfigure(parent,rng,side_cap,attempts=40)
    else:
        result,_ = propose_contact_relocate(parent,rng,side_cap,attempts=40)
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--generations",type=int,default=500)
    p.add_argument("--parents",type=int,default=20)
    p.add_argument("--offspring-per-parent",type=int,default=5)
    p.add_argument("--seed",type=int,default=2715)
    p.add_argument("--structural-probability",type=float,default=0.35)
    p.add_argument("--exploration-side-cap",type=float,default=3.8,
                   help="Permit intermediate valid layouts larger than initial L=3")
    p.add_argument("--historical-jump-every",type=int,default=20,
                   help="Reintroduce a genuine archived historical parent at this interval after stagnation; 0 disables")
    p.add_argument("--historical-stagnation-after",type=int,default=30)
    p.add_argument("--legacy-center-operator",action="store_true",
                   help="Reproduce previous fixed-corner specialist for comparison only")
    p.add_argument("--no-structural",action="store_true",
                   help="Control: real generations with only Gerit's original coordinated operator")
    p.add_argument("--report-every",type=int,default=10,
                   help="Print live progress in the terminal every N generations (default: 10)")
    p.add_argument("--image-every",type=int,default=25,
                   help="Keep generation logs for every generation; save population PNG every N generations")
    p.add_argument("--out",type=Path,default=Path("results/five-square-evolution-500"))
    a=p.parse_args()
    if a.generations < 1 or a.parents < 2 or a.offspring_per_parent < 1:
        p.error("generations>=1, parents>=2, offspring-per-parent>=1 required")
    if a.image_every < 1:
        p.error("image-every must be >=1")
    if a.report_every < 1:
        p.error("report-every must be >=1")
    if a.exploration_side_cap < 3 or not math.isfinite(a.exploration_side_cap):
        p.error("exploration-side-cap must be finite and >=3")
    if not 0 <= a.structural_probability <= 1:
        p.error("structural-probability must be between 0 and 1")
    if a.historical_jump_every < 0 or a.historical_stagnation_after < 1:
        p.error("historical jump settings invalid")
    if a.out.exists():
        raise FileExistsError(f"Refusing to overwrite previous results: {a.out}")
    initial=corner_center_seed()
    assert initial.container_side == 3 and validate_packing(initial,tolerance=0).valid
    cfg=replace(load_config(ROOT/"configs/five-squares.json"),
                initial_population=a.parents,next_generation_population=a.parents,
                offspring_per_parent=a.offspring_per_parent,
                max_generations=a.generations,
                max_evaluations=a.generations*a.parents*a.offspring_per_parent+10000,
                seed=a.seed)
    start_time=time.perf_counter()
    print(f"START N=5 | generations={a.generations} | parents={a.parents} | "
          f"offspring/parent={a.offspring_per_parent} | report-every={a.report_every}",flush=True)
    def report_progress(generation):
        g=generation.generation
        if g == 0 or g % a.report_every == 0 or g == a.generations:
            elapsed=time.perf_counter()-start_time
            print(f"GEN {g:4d}/{a.generations} | best_L={generation.best_side:.12f} | "
                  f"score={puzzle_score(5,generation.best_side):.10f} | "
                  f"evaluations={generation.evaluations} | "
                  f"valid_children={generation.valid_children} | "
                  f"rotated_parents={generation.rotated_parents}/{a.parents} | "
                  f"geometric_distinct={generation.geometric_distinct} | "
                  f"historical_jumps={generation.historical_jumps} | "
                  f"population_max_L={generation.max_population_side:.6f} | "
                  f"elapsed={elapsed:.1f}s",flush=True)
    # The supplied geometry is ONLY the INITIAL seed: from here on every
    # square is freely rotated, relocated, expanded and contracted.
    if a.no_structural:
        chosen_mutator=None
    elif a.legacy_center_operator:
        chosen_mutator=corner_center_mutation
    else:
        chosen_mutator=lambda parent,rng:free_structure_mutation(parent,rng,a.exploration_side_cap)
    result=evolve(cfg,output_dir=str(a.out),image_columns=4,coordinated=True,
                  initial_seed=initial,
                  structural_mutator=chosen_mutator,
                  structural_probability=a.structural_probability,
                  image_every=a.image_every,
                  progress_callback=report_progress,
                  exploration_side_cap=a.exploration_side_cap,
                  historical_jump_every=a.historical_jump_every,
                  historical_stagnation_after=a.historical_stagnation_after)
    assert len(result.history)==a.generations+1
    assert result.history[0].generation==0
    assert all(row.generation==index for index,row in enumerate(result.history))
    poses=tuple((repr(s.x),repr(s.y),repr(s.angle)) for s in result.best.squares)
    checked=validate(Candidate(5,poses,"Gerit real evolution",result.best.container_side))
    if not checked.valid:
        raise RuntimeError("Independent Kaggle interval validation failed: "+checked.reason)
    summary={
        "mode":"gerit.evolution.evolve_real_generations",
        "initial_seed":"four_corners_one_center_all_zero_rotation",
        "initial_L":3.0,
        "generations":len(result.history)-1,
        "parents":a.parents,"offspring_per_parent":a.offspring_per_parent,
        "image_every":a.image_every,
        "report_every":a.report_every,
        "evaluations":result.evaluations,"accepted_children":result.accepted_children,
        "structural_hook_enabled":not a.no_structural,
        "structural_operator":("disabled" if a.no_structural else
                               "legacy_fixed_corners" if a.legacy_center_operator else
                               "all_squares_free_reconfigure_or_contact_relocate"),
        "exploration_side_cap":a.exploration_side_cap,
        "historical_jump_every":a.historical_jump_every,
        "historical_stagnation_after":a.historical_stagnation_after,
        "rotated_best_squares":sum(abs(math.sin(2*s.angle))>1e-7 for s in result.best.squares),
        "seed":a.seed,"best_L":checked.side,
        "best_score":puzzle_score(5,checked.side),
        "grid_baseline_score":baseline_score(5),
        "score_gain":baseline_score(5)-puzzle_score(5,checked.side),
        "interval_validation":checked.reason,
        "generation_0_best_L":result.history[0].best_side,
        "last_generation_best_L":result.history[-1].best_side,
        "evolutionary_improvement":result.history[0].best_side-result.history[-1].best_side,
        "best_poses":[asdict(s) for s in result.best.squares],
        "history":[asdict(h) for h in result.history]
    }
    (a.out/"kaggle_evolution_comparison.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps({k:v for k,v in summary.items() if k not in ("history","best_poses")},indent=2))


if __name__=="__main__":
    main()
