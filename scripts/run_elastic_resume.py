"""Resume Gerit's N=230 elastic packing from a saved near-feasible checkpoint.

Strictly read-only by default. Does not reset the genetic/historical
optimizer. Each attempt starts from the saved best-near-feasible pose,
perturbs a small group of high-violation squares, then reoptimizes ALL
coordinates and rotations with escalating collision penalties.
The source NPZ is never overwritten. A new NPZ holds a better invalid
candidate for further retries.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
import numpy as np

from gerit.elastic_growth import certified_candidate,relax_once
from gerit.elastic_repair import feasibility_diagnostics
from gerit.kaggle import Candidate,validate as interval_validate
from scripts.kaggle_best_registry import read_registry,propose_improvement


def _load_checkpoint(path,n):
    with np.load(path,allow_pickle=False) as item:
        poses=np.array(item["poses"],dtype=float)
        target=int(item["target_n"])
        cap=float(item["side_cap"])
    if target != n or poses.shape!=(n,3) or not np.all(np.isfinite(poses)):
        raise ValueError("Checkpoint target N, shape or finite values invalid")
    if not math.sqrt(n)<cap<math.ceil(math.sqrt(n)):
        raise ValueError("Checkpoint cap must beat the current grid bound")
    return poses,cap


def _severity(d):
    # Keep penetration and boundary excess as the primary ranking.
    # Count is a tie-breaker only; never accept an invalid solution.
    return d["total_penetration"]+d["boundary_total"]


def _perturb(pose,diag,rng,scale,group_size):
    new=pose.copy()
    n=len(new)
    hot=set()
    for i,j,depth in diag["worst_pairs"]:
        hot.update((i,j))
    ext=.5*(np.abs(np.sin(new[:,2]))+np.abs(np.cos(new[:,2])))
    indices=np.where((new[:,0]<ext)|(new[:,1]<ext)|
                     (new[:,0]>new._cap-ext)|
                     (new[:,1]>new._cap-ext))[0] if False else []
    # Prefer affected neighbors, but allow long-range escape jumps.
    if rng.random()<.75 and hot:
        idx=list(hot)
        rng.shuffle(idx)
        selection=idx[:group_size]
        if len(selection)<group_size:
            more=[i for i in range(n) if i not in selection]
            selection+=rng.choice(more,size=min(group_size-len(selection),len(more)),
                                  replace=False).tolist()
    else:
        selection=rng.choice(n,size=min(group_size,n),replace=False).tolist()
    new[selection,:2]+=rng.normal(0.,scale,size=(len(selection),2))
    new[selection,2]+=rng.normal(0.,scale*.45,size=len(selection))
    new[:,2]=((new[:,2]+math.pi/4)%(math.pi/2))-math.pi/4
    return new


def run(*,registry,checkpoint,n=230,attempts=32,
        iterations=400,seed=230,group_size=12,
        report,output_checkpoint,apply=False,report_every=4):
    if not 2<=n<=1000 or attempts<1 or iterations<1 or group_size<1 or report_every<1:
        raise ValueError("Invalid experiment settings")
    for destination in (report,output_checkpoint):
        if Path(destination).exists():
            raise FileExistsError(f"Refusing to overwrite: {destination}")
    original,cap=_load_checkpoint(checkpoint,n)
    bank=read_registry(registry)
    old_side=float(bank["problems"][str(n)]["side"])
    cap=min(cap,old_side-.00001)
    if cap<=math.sqrt(n):
        raise ValueError("Target cap does not exceed area bound")
    base_diag=feasibility_diagnostics(original,cap)
    best_invalid=original.copy()
    best_diag=base_diag
    best_valid=None
    rows=[]
    rng=np.random.default_rng(seed)
    print(f"RESUME N={n} cap={cap:.10f} "
          f"checkpoint_pairs={base_diag['overlap_pairs']} "
          f"checkpoint_outside={base_diag['outside_squares']} "
          f"checkpoint_violation={_severity(base_diag):.9g}",flush=True)
    # Attempt zero: refine unchanged checkpoint first, before random kicks.
    for trial in range(attempts):
        if trial==0:
            pose=best_invalid.copy()
            scale=0.
        else:
            pose=_perturb(best_invalid,best_diag,rng,
                          scale=(.004,.012,.04,.12)[(trial-1)%4],
                          group_size=group_size)
        step=(1e3,1e4,1e5,1e6) if trial%3 else (1e2,1e3,1e4,1e5,1e6)
        result,loss,used=relax_once(
            pose,cap,iterations=iterations,penalty_schedule=step,
            angle_weight=0.)
        diag=feasibility_diagnostics(result,cap)
        if _severity(diag)<_severity(best_diag)-1e-15:
            best_invalid=result.copy()
            best_diag=diag
        candidate=certified_candidate(result,cap)
        is_valid=False
        reason="strict SAT rejected"
        if candidate:
            verdict=interval_validate(Candidate(
                n,tuple((repr(s.x),repr(s.y),repr(s.angle))
                        for s in candidate.squares),
                "elastic_checkpoint_resume",candidate.container_side))
            is_valid=verdict.valid
            reason=verdict.reason
            if is_valid and (best_valid is None or
                             candidate.container_side<best_valid.container_side):
                best_valid=candidate
                print(f"CERTIFIED trial={trial+1} "
                      f"L={candidate.container_side:.12f}",flush=True)
        rows.append({"trial":trial+1,"energy":loss,"iterations":used,
                     "scale":scale,"valid":is_valid,"reason":reason,
                     "diagnostics":diag})
        if (trial+1)%report_every==0 or trial+1==attempts:
            print(f"TRIAL {trial+1}/{attempts} "
                  f"pairs={diag['overlap_pairs']} "
                  f"max_penetration={diag['max_penetration']:.6g} "
                  f"outside={diag['outside_squares']} "
                  f"nearest_violation={_severity(best_diag):.9g} "
                  f"certified={best_valid is not None}",flush=True)
    updated=False
    if apply and best_valid:
        offer=propose_improvement(
            registry,{"n":n,"side":best_valid.container_side,
                      "squares":[asdict(s) for s in best_valid.squares]},
            source="gerit_elastic_checkpoint_resume",
            experiment_id=f"elastic-resume-n{n}-seed{seed}-a{attempts}",
            generation=attempts,operator="collective_sat_checkpoint_repair")
        updated=bool(offer["accepted"])
    result={
        "n":n,"seed":seed,"source_checkpoint":str(checkpoint),
        "previous_side":old_side,"target_cap":cap,
        "checkpoint_diagnostics":base_diag,
        "nearest_diagnostics":best_diag,
        "accepted_count":int(best_valid is not None),
        "best_certified_side":best_valid.container_side if best_valid else None,
        "applied":updated,"initial_score":bank["total_score"],
        "final_score":read_registry(registry)["total_score"] if updated
            else (bank["total_score"]+(best_valid.container_side-old_side)/math.sqrt(n)
                  if best_valid else bank["total_score"]),
        "trials":rows}
    Path(report).parent.mkdir(parents=True,exist_ok=True)
    Path(report).write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    Path(output_checkpoint).parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(output_checkpoint,poses=best_invalid,
                        side_cap=np.array(cap),
                        source_n=np.array(n-1),target_n=np.array(n),
                        seed=np.array(seed))
    print(f"FINISHED N={n} certified={best_valid is not None} "
          f"updated={updated} best_L={result['best_certified_side']} "
          f"score={result['final_score']:.12f}",flush=True)
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--registry",default="results/kaggle_baseline/best_registry.json")
    p.add_argument("--checkpoint",default="results/kaggle_elastic_growth/n230_nearest.npz")
    p.add_argument("--n",type=int,default=230)
    p.add_argument("--attempts",type=int,default=32)
    p.add_argument("--iterations",type=int,default=400)
    p.add_argument("--seed",type=int,default=230)
    p.add_argument("--group-size",type=int,default=12)
    p.add_argument("--report-every",type=int,default=4)
    p.add_argument("--report",default="results/kaggle_elastic_growth/n230_resume.json")
    p.add_argument("--output-checkpoint",default="results/kaggle_elastic_growth/n230_resume_nearest.npz")
    p.add_argument("--apply",action="store_true")
    a=p.parse_args()
    run(registry=a.registry,checkpoint=a.checkpoint,n=a.n,
        attempts=a.attempts,iterations=a.iterations,seed=a.seed,
        group_size=a.group_size,report=a.report,
        output_checkpoint=a.output_checkpoint,
        apply=a.apply,report_every=a.report_every)

if __name__=="__main__":
    main()
