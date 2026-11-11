"""N17/N18/N19 geometric-founder and two-parent evolution experiments.

Reuses Gerit's original fitness/diversity survival and historical archive.
Run in CMD: py -3 -u scripts/run_symmetry_three_counts.py --generations 50
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

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from gerit.config import load_config
from gerit.evolution import evolve, packing_distance
from gerit.geometry import grid_baseline, validate_packing
from gerit.kaggle import Candidate, puzzle_score, validate
from gerit.symmetry_operators import (geometry_seed_bank,
    multi_parent_quadrant_crossover, propose_symmetry_group_move, OPERATORS)
from scripts.run_three_square_counts import (
    geometry_only_mutation, PUBLISHED_REFERENCE_L)

def prepare_founders(n, seed, parents, cap):
    bank=geometry_seed_bank(n, seed, copies=4)
    # Reserve distinct structural families before sampling extra candidates.
    rank={name:i for i,name in enumerate(("four_corner_clusters",
        "fourfold","diagonal_pairs","horizontal","vertical",
        "corner_first","random_sparse","grid"))}
    bank.sort(key=lambda row:(rank.get(row[0],99), row[1].container_side))
    chosen=[("grid",grid_baseline(n))]
    for name,p in bank:
        if p.container_side>cap+1e-9:
            continue
        if any(abs(p.container_side-q.container_side)<1e-8 and
                packing_distance(p,q)<1e-7 for _,q in chosen):
            continue
        chosen.append((name,p))
        if len(chosen)>=parents:
            break
    return chosen

def run_one(n,a,root):
    baseline=grid_baseline(n)
    cap=baseline.container_side+a.exploration_extra_side
    seed=a.seed+n
    founders=prepare_founders(n, seed, a.parents, cap)
    print(f"\n{'='*64}\nSTART N={n} | founder_count={len(founders)} | "
          f"families={[name for name,_ in founders]} | cap={cap:.3f}",flush=True)
    for name,p in founders:
        print(f"  FOUNDER {name:<23} L={p.container_side:.12f}",flush=True)
    cfg=replace(load_config(ROOT/"configs/five-squares.json"),
        n_squares=n,initial_container_side=baseline.container_side,
        initial_population=a.parents,next_generation_population=a.parents,
        offspring_per_parent=a.offspring_per_parent,
        max_generations=a.generations,
        max_evaluations=a.generations*a.parents*a.offspring_per_parent+10000,
        seed=seed)
    start=time.perf_counter()
    def progress(g):
        if g.generation==0 or g.generation%a.report_every==0 or g.generation==a.generations:
            print(f"N={n} GEN {g.generation:4d}/{a.generations} | "
                  f"best_L={g.best_side:.12f} | score={puzzle_score(n,g.best_side):.9f} "
                  f"| valid_children={g.valid_children} | "
                  f"distinct={g.geometric_distinct}/{a.parents} "
                  f"| historical_jumps={g.historical_jumps} "
                  f"| elapsed={time.perf_counter()-start:.1f}s",flush=True)
    def symmetry_or_generic(parent,rng):
        if rng.random()<a.symmetry_mutation_share:
            return propose_symmetry_group_move(parent,rng,cap,attempts=35)
        return geometry_only_mutation(parent,rng,cap,a.contact_probability)
    result=evolve(cfg,output_dir=str(root),image_columns=4,
        coordinated=True,
        initial_seed=founders[0][1],
        initial_seeds=tuple(p for _,p in founders[1:]),
        structural_mutator=symmetry_or_generic,
        structural_probability=a.structural_probability,
        multi_parent_mutator=lambda p,q,rng: multi_parent_quadrant_crossover(p,q,rng,cap),
        multi_parent_probability=a.multi_parent_probability,
        exploration_side_cap=cap,
        image_every=a.image_every,progress_callback=progress,
        historical_jump_every=a.historical_jump_every,
        historical_stagnation_after=a.historical_stagnation_after)
    candidate=Candidate(n,tuple((repr(s.x),repr(s.y),repr(s.angle))
                      for s in result.best.squares),
                      "Gerit symmetry multi-parent evolution",result.best.container_side)
    check=validate(candidate)
    if not check.valid:
        raise RuntimeError(f"N={n} failed independent interval SAT: {check.reason}")
    summary={
        "n":n,"seed":seed,"generations":len(result.history)-1,
        "initial_grid_L":baseline.container_side,
        "best_founder_L":min(p.container_side for _,p in founders),
        "founder_names":[name for name,_ in founders],
        "best_L":check.side,"score":puzzle_score(n,check.side),
        "published_reference_L":PUBLISHED_REFERENCE_L[n],
        "gap_to_published_reference":check.side-PUBLISHED_REFERENCE_L[n],
        "reference_not_used_for_evolution":True,
        "independent_validation":check.reason,
        "evaluations":result.evaluations,
        "accepted_children":result.accepted_children,
        "multi_parent_probability":a.multi_parent_probability,
        "structural_probability":a.structural_probability,
        "symmetry_mutation_share":a.symmetry_mutation_share,
        "elapsed_seconds":time.perf_counter()-start,
        "best_squares":[asdict(s) for s in result.best.squares],
    }
    root.joinpath("experiment_summary.json").write_text(
        json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    root.joinpath("best_packing.json").write_text(json.dumps(
        {"side":check.side,"squares":summary["best_squares"]},indent=2)+"\n",
        encoding="utf-8")
    print(f"COMPLETE N={n} | L={check.side:.12f} | "
          f"vs published={summary['gap_to_published_reference']:+.9f} "
          f"| verified={check.reason}",flush=True)
    return {k:v for k,v in summary.items() if k!="best_squares"}

def main(argv=None):
    p=argparse.ArgumentParser(description="Sequential N17/N18/N19 multi-founder geometry experiments")
    p.add_argument("--counts",nargs="+",type=int,choices=(17,18,19),default=[17,18,19])
    p.add_argument("--generations",type=int,default=50)
    p.add_argument("--parents",type=int,default=20)
    p.add_argument("--offspring-per-parent",type=int,default=5)
    p.add_argument("--seed",type=int,default=2715)
    p.add_argument("--report-every",type=int,default=10)
    p.add_argument("--image-every",type=int,default=10)
    p.add_argument("--exploration-extra-side",type=float,default=.8)
    p.add_argument("--structural-probability",type=float,default=.30)
    p.add_argument("--multi-parent-probability",type=float,default=.20)
    p.add_argument("--contact-probability",type=float,default=.35)
    p.add_argument("--symmetry-mutation-share",type=float,default=.40)
    p.add_argument("--historical-jump-every",type=int,default=20)
    p.add_argument("--historical-stagnation-after",type=int,default=30)
    p.add_argument("--out-root",type=Path,default=Path("results/n17-n18-n19-symmetry"))
    a=p.parse_args(argv)
    if len(set(a.counts))!=len(a.counts):p.error("Repeated N")
    if a.generations<1 or a.parents<2 or a.offspring_per_parent<1:p.error("invalid population/generations")
    if a.report_every<1 or a.image_every<1:p.error("invalid interval")
    if a.exploration_extra_side<0 or not math.isfinite(a.exploration_extra_side):p.error("invalid extra side")
    if a.structural_probability<0 or a.multi_parent_probability<0 or a.structural_probability+a.multi_parent_probability>1:p.error("invalid probabilities")
    if not 0<=a.symmetry_mutation_share<=1:p.error("invalid symmetry share")
    if a.out_root.exists():p.error(f"Output exists: {a.out_root}")
    a.out_root.mkdir(parents=True)
    completed=[]
    try:
        for n in a.counts:
            dest=a.out_root/f"n{n}"
            dest.mkdir()
            completed.append(run_one(n,a,dest))
            (a.out_root/"sequential_summary.json").write_text(
                json.dumps({"status":"in_progress","completed":completed},indent=2)+"\n",
                encoding="utf-8")
    except Exception as exc:
        (a.out_root/"sequential_summary.json").write_text(
            json.dumps({"status":"failed","completed":completed,"error":repr(exc)},indent=2)+"\n",
            encoding="utf-8")
        raise
    (a.out_root/"sequential_summary.json").write_text(
        json.dumps({"status":"completed","completed":completed},indent=2)+"\n",
        encoding="utf-8")
    print("\nALL DONE "+", ".join(f"N={r['n']} L={r['best_L']:.9f}" for r in completed),flush=True)

if __name__=="__main__":
    main()
