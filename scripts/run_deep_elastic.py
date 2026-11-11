"""Deep iterative improvement of an already-certified N-square Gerit packing.

Unlike N->N+1 growth, this run has a FIXED square count. It keeps a
multi-scale archive of feasible and near-feasible packings, mutates and
rotates *any* square, and repeatedly tries strictly smaller container
targets. The original evolutionary engine and historical jumps are not
changed.

- Every certified improvement is persisted to an experiment directory,
  even on a dry run; with --apply it also updates the 1000-case registry.
- Progress prints every 10 generations by default.
- Run is reproducible with a random seed and resumable via --resume-dir.
- Only strict SAT + independent interval SAT permit registry updates.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import asdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
import numpy as np

from gerit.elastic_growth import certified_candidate,relax_once
from gerit.elastic_repair import feasibility_diagnostics
from gerit.geometry import Packing,Square,minimum_bounding_square,validate_packing
from gerit.kaggle import Candidate,validate as interval_validate
from scripts.kaggle_best_registry import read_registry,propose_improvement


FAMILY="elastic_deep_fixed_n"


def _packing_record(p: Packing):
    return {"n":len(p.squares),"side":p.container_side,
            "squares":[asdict(s) for s in p.squares]}


def _packing_from_record(entry):
    return Packing(tuple(Square(float(s["x"]),float(s["y"]),float(s["angle"]))
                         for s in entry["squares"]),float(entry["side"]))


def _coords(p: Packing):
    return np.array([(s.x,s.y,s.angle) for s in p.squares],dtype=float)


def _write_json(path:Path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+".tmp")
    try:
        with temp.open("w",encoding="utf-8") as fp:
            json.dump(obj,fp,indent=2,allow_nan=False)
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(temp,path)
    finally:
        temp.unlink(missing_ok=True)


def _certify(p: Packing):
    if not validate_packing(p,tolerance=0.).valid:
        return False,"strict SAT overlap"
    verdict=interval_validate(Candidate(
        len(p.squares),tuple((repr(s.x),repr(s.y),repr(s.angle))
                             for s in p.squares),
        FAMILY,p.container_side))
    return verdict.valid,verdict.reason


def _mutate(pose,rng,scale,*,mode):
    result=pose.copy()
    n=len(result)
    if mode==0:
        # Collective compression creates temporary collision on purpose:
        # solve it by moving and rotating all affected squares.
        center=np.mean(result[:,:2],axis=0)
        fraction=float(rng.uniform(.0001,max(.0002,scale*.06)))
        result[:,:2]=center+(result[:,:2]-center)*(1.-fraction)
    elif mode==1:
        # Local cluster shake, allowing every member to rotate.
        anchor=rng.integers(n)
        xy=result[:,:2]
        radii=np.sum((xy-xy[anchor])**2,axis=1)
        size=min(n,int(rng.choice([4,8,16,32,64])))
        ids=np.argpartition(radii,size-1)[:size]
        result[ids,:2]+=rng.normal(0.,scale,size=(size,2))
        result[ids,2]+=rng.normal(0.,scale*.5,size=size)
    elif mode==2:
        # Long-range historical-style partial reset.
        ids=rng.choice(n,size=min(n,int(rng.choice([5,15,40]))),replace=False)
        result[ids,:2]+=rng.normal(0.,scale*2.,size=(len(ids),2))
        result[ids,2]+=rng.normal(0.,scale,size=len(ids))
    elif mode==3:
        # Global small changes to every square: freedom for all 3N DOF.
        result[:,:2]+=rng.normal(0.,scale*.25,size=(n,2))
        result[:,2]+=rng.normal(0.,scale*.12,size=n)
    else:
        # Rotate an entire local group and translate it together,
        # retaining its internal arrangement until relaxation.
        pivot=int(rng.integers(n))
        xy=result[:,:2]
        k=min(n,int(rng.choice([8,16,32])))
        selected=np.argpartition(np.sum((xy-xy[pivot])**2,axis=1),k-1)[:k]
        center=np.mean(xy[selected],axis=0)
        angle=float(rng.normal(0.,scale*.5))
        co,si=np.cos(angle),np.sin(angle)
        rotation=np.array([[co,-si],[si,co]])
        result[selected,:2]=(xy[selected]-center)@rotation.T+center
        result[selected,2]+=angle
    # Squares have pi/2 rotational symmetry.
    result[:,2]=(result[:,2]+math.pi/4)%(math.pi/2)-math.pi/4
    return result


def _ranking(d):
    return d["total_penetration"]+d["boundary_total"]


def optimize(*,registry,n=230,generations=900,iterations=160,
             seed=2300,log_every=10,output_dir,apply=False,
             resume_dir=None,shrink_max=.035):
    if not 2<=n<=1000 or generations<1 or iterations<1 or log_every<1:
        raise ValueError("Invalid N or budgets")
    if not 0<shrink_max<=.2:
        raise ValueError("shrink-max must be (0,0.2]")
    output=Path(output_dir)
    if output.exists():
        raise FileExistsError(f"Experiment folder already exists: {output}")
    bank=read_registry(registry)
    archive=_packing_from_record(bank["problems"][str(n)])
    valid,why=_certify(archive)
    if not valid:
        raise ValueError(f"Registry founder fails independent certification: {why}")
    current_registry_side=archive.container_side
    best=archive
    near=None
    near_diag=None
    near_cap=None
    resumed_from=None
    if resume_dir is not None:
        src=Path(resume_dir)
        past=json.loads((src/"progress.json").read_text(encoding="utf-8"))
        if int(past["n"])!=n:
            raise ValueError("Resume checkpoint uses a different N")
        saved=json.loads((src/"best_valid.json").read_text(encoding="utf-8"))
        restored=_packing_from_record(saved)
        confirmed,reason=_certify(restored)
        if not confirmed:
            raise ValueError(f"Resumed packing fails certification: {reason}")
        if restored.container_side<best.container_side-1e-10:
            best=restored
        nearfile=src/"best_near.npz"
        if nearfile.exists():
            with np.load(nearfile,allow_pickle=False) as obj:
                array=np.array(obj["poses"],dtype=float)
                l=float(obj["cap"])
            if array.shape==(n,3) and np.isfinite(array).all() and math.sqrt(n)<l<32:
                near=array
                near_cap=l
                near_diag=feasibility_diagnostics(array,l)
        resumed_from=str(src)
    rng=np.random.default_rng(seed)
    # Reserve output only after validation; never delete previous results.
    output.mkdir(parents=True)
    _write_json(output/"best_valid.json",_packing_record(best))
    _write_json(output/"configuration.json",{
        "n":n,"generations":generations,"iterations":iterations,
        "seed":seed,"log_every":log_every,"shrink_max":shrink_max,
        "registry_start_side":current_registry_side,
        "resumed_from":resumed_from,"method":FAMILY})
    certified=0
    updates=0
    nearest_changes=0
    history=[]
    # Keep several valid historical elites for exploration rather than
    # relying only on the current incumbent.
    elites=[best]
    no_progress=0
    start_score=float(bank["total_score"])
    lower_bound=math.sqrt(n)
    for generation in range(1,generations+1):
        mode=(generation-1)%5
        if near is not None and generation%4==0:
            initial=near.copy()
        else:
            founder=elites[int(rng.integers(len(elites)))] if generation%7==0 else best
            initial=_coords(founder)
        scale=[.002,.01,.035,.08,.16][(generation-1)%5]
        # Escapes may go farther when a basin stagnates.
        if no_progress>60:
            scale*=1.75
        pose=_mutate(initial,rng,scale,mode=mode)
        # Tighten by a spectrum of strict improvements, not merely <16.
        target_decrease=[.000025,.0002,.001,.005,.02,shrink_max][(generation-1)%6]
        cap=max(lower_bound+1e-4,best.container_side-target_decrease)
        if near is not None and generation%4==0:
            cap=min(cap,near_cap)
        if cap<=lower_bound+1e-7:
            continue
        schedule=(1.,10.,100.,1000.) if generation%3 else (10.,100.,1000.,10000.)
        solution,energy,used=relax_once(
            pose,cap,iterations=iterations,penalty_schedule=schedule,
            angle_weight=0.)
        if generation%4==0 or energy<1e-5:
            solution,energy2,extra=relax_once(
                solution,cap,iterations=max(40,iterations//2),
                penalty_schedule=(1e3,1e4,1e5),angle_weight=0.)
            energy=energy2
            used+=extra
        diag=feasibility_diagnostics(solution,cap)
        if near_diag is None or _ranking(diag)<_ranking(near_diag)-1e-13:
            near=solution.copy()
            near_diag=diag
            near_cap=cap
            nearest_changes+=1
            np.savez_compressed(output/"best_near.npz",
                                poses=near,cap=np.array(cap),
                                target_n=np.array(n),seed=np.array(seed))
        candidate=certified_candidate(solution,cap)
        is_better=False
        if candidate is not None and candidate.container_side<best.container_side-1e-10:
            is_valid,reason=_certify(candidate)
            if is_valid:
                certified+=1
                previous=best.container_side
                best=candidate
                elites.append(candidate)
                elites=sorted(elites,key=lambda p:p.container_side)[:8]
                _write_json(output/"best_valid.json",_packing_record(best))
                is_better=True
                no_progress=0
                print(f"CERTIFIED gen={generation}/{generations} "
                      f"N={n} old_L={previous:.12f} "
                      f"new_L={best.container_side:.12f}",flush=True)
                if apply and best.container_side<current_registry_side-1e-10:
                    offer=propose_improvement(
                        registry,_packing_record(best),
                        source="gerit_deep_elastic_compression",
                        experiment_id=f"deep-elastic-n{n}-s{seed}-g{generation}",
                        generation=generation,operator=FAMILY)
                    if offer["accepted"]:
                        current_registry_side=best.container_side
                        updates+=1
        if not is_better:
            no_progress+=1
        if generation%log_every==0 or generation==generations:
            expected_score=start_score+(best.container_side-archive.container_side)/math.sqrt(n)
            if apply:
                expected_score=float(read_registry(registry)["total_score"])
            record={
                "generation":generation,"n":n,"best_side":best.container_side,
                "certified_updates":certified,"registry_updates":updates,
                "near_violation":_ranking(near_diag) if near_diag else None,
                "near_collisions":near_diag["overlap_pairs"] if near_diag else None,
                "near_outside":near_diag["outside_squares"] if near_diag else None,
                "stagnation":no_progress,"projected_score":expected_score}
            history.append(record)
            _write_json(output/"progress.json",{
                "n":n,"finished_generation":generation,
                "generations_requested":generations,
                "initial_side":archive.container_side,
                "best_side":best.container_side,
                "improvement":archive.container_side-best.container_side,
                "certified_updates":certified,
                "registry_updates":updates,"nearest_changes":nearest_changes,
                "initial_score":start_score,"score":expected_score,
                "checkpoint":str(output/"best_valid.json"),
                "near_checkpoint":str(output/"best_near.npz"),
                "history":history})
            print(f"STEP {generation}/{generations} N={n} "
                  f"best_L={best.container_side:.12f} "
                  f"near_pairs={record['near_collisions']} "
                  f"near_outside={record['near_outside']} "
                  f"certified={certified} stagnation={no_progress} "
                  f"score={expected_score:.12f}",flush=True)
    return {"n":n,"best_side":best.container_side,
            "initial_side":archive.container_side,
            "certified_updates":certified,"registry_updates":updates,
            "output_dir":str(output)}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--registry",default="results/kaggle_baseline/best_registry.json")
    p.add_argument("--n",type=int,default=230)
    p.add_argument("--generations",type=int,default=900)
    p.add_argument("--iterations",type=int,default=160)
    p.add_argument("--seed",type=int,default=2300)
    p.add_argument("--log-every",type=int,default=10)
    p.add_argument("--shrink-max",type=float,default=.035)
    p.add_argument("--output-dir",default="results/kaggle_deep/n230_g900_s2300")
    p.add_argument("--resume-dir")
    p.add_argument("--apply",action="store_true")
    args=p.parse_args()
    optimize(registry=args.registry,n=args.n,
             generations=args.generations,iterations=args.iterations,
             seed=args.seed,log_every=args.log_every,
             output_dir=args.output_dir,apply=args.apply,
             resume_dir=args.resume_dir,shrink_max=args.shrink_max)


if __name__=="__main__":
    main()
