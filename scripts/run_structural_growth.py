"""Structural N-1 -> N growth with diverse insertion and near-feasible archives.

Experimental: does not change the classic evolutionary engine or registry.
The best N-1 certified founder is taken from the bank or --source-file.
A certified N packing is a prerequisite for deep compression. If growth
fails, preserve near states and DO NOT waste 500 deep generations on the
unrelated N grid fallback. All poses and angles remain movable.
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
from scipy.spatial import cKDTree
from gerit.elastic_growth import relax_once,certified_candidate
from gerit.elastic_repair import feasibility_diagnostics,repair_relaxation
from gerit.geometry import Packing,Square,minimum_bounding_square,validate_packing
from gerit.kaggle import Candidate,validate
from gerit.packing_io import load_packing_json
from scripts.kaggle_best_registry import read_registry
from scripts.run_deep_elastic import optimize,_packing_from_record,_certify,_write_json

def _score(diag):
    return (diag["total_penetration"] + diag["boundary_total"],
            diag["overlap_pairs"],diag["outside_squares"])

def _founder(bank,n,source_file=None):
    record=(load_packing_json(source_file) if source_file
            else bank["problems"][str(n-1)])
    if int(record["n"])!=n-1:
        raise ValueError("Founder must contain exactly N-1 squares")
    founder=_packing_from_record(record)
    ok,why=_certify(founder)
    if not ok:
        raise ValueError(f"Founder failed certification: {why}")
    return minimum_bounding_square(founder.squares)

def _insertion(founder,cap,rng,style):
    """Place new square at several spatially distinct sites; displace local
    neighbours to create space without locking any of the old squares.
    """
    xy=np.array([(s.x,s.y) for s in founder.squares],dtype=float)
    angles=np.array([s.angle for s in founder.squares],dtype=float)
    poses=np.column_stack((xy,angles))
    # Founder coordinates already occupy a slightly smaller envelope.
    poses[:,:2]+=.5*(cap-founder.container_side)
    anchors=poses[:,:2]
    n=len(poses)
    # Generate a diverse set of interior and boundary-biased sites. A
    # candidate is chosen by balancing crowding and boundary feasibility.
    sites=rng.uniform(.55,cap-.55,size=(48,2))
    if style%4==0:
        # Corner/edge exploration.
        fixed=rng.choice([.55,cap-.55],size=(24,2))
        fixed[:,rng.integers(0,2)]=rng.uniform(.55,cap-.55,size=24)
        sites=np.vstack((sites,fixed))
    elif style%4==1:
        # Open a hole near a random existing square, allowing rotations.
        ids=rng.choice(n,size=24,replace=False)
        sites=np.vstack((sites,anchors[ids]+rng.normal(0,.3,size=(24,2))))
    elif style%4==2:
        # Explicit near-edge insertion with a free side coordinate.
        fixed=rng.uniform(.55,cap-.55,size=(24,2))
        axis=int(rng.integers(0,2))
        fixed[:,axis]=rng.choice([.55,cap-.55],size=24)
        sites=np.vstack((sites,fixed))
    else:
        sites=np.vstack((sites,rng.uniform(.55,cap-.55,size=(24,2))))
    sites=np.clip(sites,.55,cap-.55)
    distance,_=cKDTree(anchors).query(sites,k=1)
    # Avoid selecting the most impossible location; favor sites with
    # existing space, randomized to keep multiple structural basins.
    ranks=np.argsort(distance)[-max(8,len(distance)//5):]
    site=sites[int(rng.choice(ranks))]
    # Local structural release: radial push followed by rigid cluster
    # rotation. All squares remain free during subsequent global repair.
    radius=float(rng.choice([1.7,2.4,3.2,4.4,6.0]))
    delta=anchors-site
    d=np.linalg.norm(delta,axis=1)
    selected=np.where(d<radius)[0]
    push=float(rng.uniform(.08,.45))
    if len(selected):
        directions=delta[selected]/np.maximum(d[selected,None],.12)
        directions[d[selected]<.12]=rng.normal(size=(np.sum(d[selected]<.12),2))
        weight=(1.-d[selected]/radius)**2
        poses[selected,:2]+=push*weight[:,None]*directions
        pivot=poses[selected,:2].mean(axis=0)
        turn=float(rng.normal(0,.045 if style%3 else .13))
        co,si=math.cos(turn),math.sin(turn)
        rot=np.array([[co,-si],[si,co]])
        poses[selected,:2]=(poses[selected,:2]-pivot)@rot.T+pivot
        poses[selected,2]+=turn+rng.normal(0,.02,size=len(selected))
    new_angle=float(rng.uniform(-math.pi/4,math.pi/4))
    return np.vstack((poses,np.array([[*site,new_angle]])))

def _distinct(archive,poses,cap,quality):
    """Keep diverse near-feasible configurations, not just the lowest loss."""
    for record in archive:
        if (np.mean(np.linalg.norm(record["poses"][:,:2]-poses[:,:2],axis=1))
            <.025):
            if quality<record["quality"]:
                record.update(poses=poses.copy(),cap=cap,quality=quality)
            return
    archive.append({"poses":poses.copy(),"cap":cap,"quality":quality})
    archive.sort(key=lambda r:r["quality"])
    del archive[8:]

def run(*,n=968,registry="results/kaggle_baseline/best_registry.json",
        source_file=None,attempts=40,iterations=300,seed=20261119,
        deep_generations=500,deep_iterations=200,output_dir):
    if not 2<=n<=1000 or attempts<1 or iterations<1 or deep_generations<0:
        raise ValueError("Invalid work budget")
    path=Path(output_dir)
    if path.exists():
        raise FileExistsError(f"Preserving previous experiment: {path}")
    bank=read_registry(registry)
    founder=_founder(bank,n,source_file)
    baseline=float(bank["problems"][str(n)]["side"])
    cap=baseline-.0005
    if cap<=math.sqrt(n):
        raise ValueError("Impossible growth cap")
    rng=np.random.default_rng(seed)
    path.mkdir(parents=True)
    _write_json(path/"configuration.json",{
        "n":n,"founder_n":n-1,"founder_side":founder.container_side,
        "registry_side":baseline,"target_cap":cap,
        "attempts":attempts,"iterations":iterations,"seed":seed,
        "deep_generations":deep_generations,
        "source_file":str(source_file) if source_file else None})
    best=None
    archive=[]
    trial_rows=[]
    for attempt in range(1,attempts+1):
        if archive and attempt%3==0:
            # Continue an independently stored near-feasible basin with
            # local shake; never fix square positions or angles.
            entry=archive[int(rng.integers(min(4,len(archive))))]
            poses=entry["poses"].copy()
            centre=int(rng.integers(n))
            dist=np.linalg.norm(poses[:,:2]-poses[centre,:2],axis=1)
            ids=np.argsort(dist)[:int(rng.choice([8,24,48,96]))]
            poses[ids,:2]+=rng.normal(0,.06,size=(len(ids),2))
            poses[ids,2]+=rng.normal(0,.035,size=len(ids))
        else:
            poses=_insertion(founder,cap,rng,attempt)
        poses[:,2]=(poses[:,2]+math.pi/4)%(math.pi/2)-math.pi/4
        relaxed,_,_=relax_once(
            poses,cap,iterations=iterations,
            penalty_schedule=(1,10,100,1000),angle_weight=0.)
        repaired,_,_=repair_relaxation(
            relaxed,cap,iterations=max(150,iterations//2))
        diag=feasibility_diagnostics(repaired,cap)
        quality=_score(diag)
        _distinct(archive,repaired,cap,quality)
        _write_json(path/"near_summary.json",[
            {"rank":i+1,"quality":list(entry["quality"])}
            for i,entry in enumerate(archive)])
        for i,entry in enumerate(archive):
            np.savez_compressed(path/f"near_{i+1:02d}.npz",
                poses=entry["poses"],side_cap=np.array(entry["cap"]),
                source_n=np.array(n-1),target_n=np.array(n))
        candidate=certified_candidate(repaired,cap)
        if candidate:
            checked=validate(Candidate(
                n,tuple((repr(s.x),repr(s.y),repr(s.angle))
                        for s in candidate.squares),
                "structural_growth",candidate.container_side))
            if checked.valid and (best is None or candidate.container_side<best.container_side):
                best=candidate
                _write_json(path/"best_growth.json",{
                    "n":n,"side":best.container_side,
                    "squares":[asdict(s) for s in best.squares]})
                print(f"CERTIFIED attempt={attempt} N={n} "
                      f"L={best.container_side:.12f}",flush=True)
        trial_rows.append({"attempt":attempt,
            "overlaps":diag["overlap_pairs"],
            "outside":diag["outside_squares"],
            "total_penetration":diag["total_penetration"],
            "boundary_total":diag["boundary_total"],
            "best_certified_side":best.container_side if best else None})
        _write_json(path/"growth_progress.json",trial_rows)
        if attempt%5==0 or attempt==attempts:
            print(f"STRUCTURAL_TRIAL {attempt}/{attempts} "
                  f"overlaps={diag['overlap_pairs']} "
                  f"outside={diag['outside_squares']} "
                  f"best_near_pairs={archive[0]['quality'][1] if archive else None} "
                  f"certified_L={best.container_side if best else None}",flush=True)
    if best is None:
        print("GROWTH_FAILED: saved diverse near_*.npz checkpoints; "
              "deep 500-generation run SKIPPED because no certified N seed.",flush=True)
        return {"certified":False,"attempts":attempts,"near":len(archive)}
    print(f"GROWTH_CERTIFIED N={n} L={best.container_side:.12f}",flush=True)
    if deep_generations:
        outcome=optimize(
            registry=registry,n=n,generations=deep_generations,
            iterations=deep_iterations,seed=seed+100000,
            log_every=10,output_dir=path/"deep",
            candidate_file=path/"best_growth.json",apply=False)
        return {"certified":True,"growth_side":best.container_side,
                "deep":outcome}
    return {"certified":True,"growth_side":best.container_side}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--n",type=int,default=968)
    p.add_argument("--registry",default="results/kaggle_baseline/best_registry.json")
    p.add_argument("--source-file")
    p.add_argument("--attempts",type=int,default=40)
    p.add_argument("--iterations",type=int,default=300)
    p.add_argument("--seed",type=int,default=20261119)
    p.add_argument("--deep-generations",type=int,default=500)
    p.add_argument("--deep-iterations",type=int,default=200)
    p.add_argument("--output-dir",default="results/kaggle_auto/structural_n968_v1")
    a=p.parse_args()
    run(n=a.n,registry=a.registry,source_file=a.source_file,
        attempts=a.attempts,iterations=a.iterations,seed=a.seed,
        deep_generations=a.deep_generations,
        deep_iterations=a.deep_iterations,output_dir=a.output_dir)

if __name__=="__main__":
    main()
