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


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--generations",type=int,default=500)
    p.add_argument("--parents",type=int,default=20)
    p.add_argument("--offspring-per-parent",type=int,default=5)
    p.add_argument("--seed",type=int,default=2715)
    p.add_argument("--structural-probability",type=float,default=0.35)
    p.add_argument("--no-structural",action="store_true",
                   help="Control: real generations with only Gerit's original coordinated operator")
    p.add_argument("--image-every",type=int,default=25,
                   help="Keep generation logs for every generation; save population PNG every N generations")
    p.add_argument("--out",type=Path,default=Path("results/five-square-evolution-500"))
    a=p.parse_args()
    if a.generations < 1 or a.parents < 2 or a.offspring_per_parent < 1:
        p.error("generations>=1, parents>=2, offspring-per-parent>=1 required")
    if a.image_every < 1:
        p.error("image-every must be >=1")
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
    result=evolve(cfg,output_dir=str(a.out),image_columns=4,coordinated=True,
                  initial_seed=initial,
                  structural_mutator=None if a.no_structural else corner_center_mutation,
                  structural_probability=a.structural_probability,
                  image_every=a.image_every)
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
        "evaluations":result.evaluations,"accepted_children":result.accepted_children,
        "structural_hook_enabled":not a.no_structural,
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
