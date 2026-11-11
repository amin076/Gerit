"""Automatic multi-family Gerit sweep with ten attempts per N by default.

Visit the first half of the *interior* of each k*k -> (k+1)*(k+1)
interval. Carry a certified N candidate forward to N+1. If the N
search fails, fall back to the bank's independently validated N
packing, rather than attempting to grow an invalid N-1 checkpoint.
This continues through later intervals without manual per-N commands.

Every attempt is saved in a persistent run directory; --resume skips
completed N and reuses the verified best file. Runs never overwrite
the best-answer bank unless --apply is explicitly requested.
"""
from __future__ import annotations
import argparse
import json
import math
import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from gerit.packing_io import load_packing_json
from scripts.kaggle_best_registry import read_registry,propose_improvement
from scripts.run_elastic_repair import run as grow
from scripts.run_deep_elastic import optimize, _packing_from_record, _packing_record, _certify


def family_targets(first=231,max_n=1000):
    """First ceil(half) of each interval's non-square integers."""
    if not 2<=first<=max_n<=1000:
        raise ValueError("Require 2 <= first <= max-n <= 1000")
    for k in range(1,math.isqrt(max_n)+1):
        low=k*k+1
        high=min(k*k+k,max_n)  # k interior values? true count=2k
        if high<low:
            continue
        for n in range(max(first,low),high+1):
            yield n


def _certified_file_or_none(file,n):
    if not file or not Path(file).is_file():
        return None
    item=load_packing_json(file)
    if int(item["n"])!=n:
        raise ValueError(f"Wrong N for certified candidate: {file}")
    p=_packing_from_record(item)
    accepted,why=_certify(p)
    if not accepted:
        raise ValueError(f"Rejecting saved packing {file}: {why}")
    return p


def _save_json(file,item):
    path=Path(file)
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+".tmp")
    try:
        with temp.open("w",encoding="utf-8") as fp:
            json.dump(item,fp,indent=2,allow_nan=False)
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(temp,path)
    finally:
        temp.unlink(missing_ok=True)


def _from_bank(bank,n):
    item=bank["problems"][str(n)]
    p=_packing_from_record(item)
    valid,reason=_certify(p)
    if not valid:
        raise ValueError(f"Bank founder N={n} rejected: {reason}")
    return p


def run(*,registry,output_dir,first=231,max_n=1000,
        attempts=10,iterations=250,deep_generations=10,
        deep_iterations=100,seed=20261112,apply=False,
        resume=False):
    if attempts<1 or iterations<1 or deep_generations<0 or deep_iterations<1:
        raise ValueError("Invalid iteration budgets")
    base=Path(output_dir)
    checkpoint=base/"sweep_state.json"
    parameters={"first":first,"max_n":max_n,"attempts":attempts,
                "iterations":iterations,"deep_generations":deep_generations,
                "deep_iterations":deep_iterations,"seed":seed,
                "registry":str(Path(registry).resolve()),"apply":apply}
    targets=list(family_targets(first,max_n))
    if resume:
        if not checkpoint.exists():
            raise FileNotFoundError(f"Resume state missing: {checkpoint}")
        state=json.loads(checkpoint.read_text(encoding="utf-8"))
        if state["parameters"]!=parameters:
            raise ValueError("Resume configuration differs: use same flags")
    else:
        if base.exists():
            raise FileExistsError(f"Experiment directory already exists: {base}")
        base.mkdir(parents=True)
        state={"parameters":parameters,"targets":targets,"results":[],
               "next_index":0}
        _save_json(checkpoint,state)
    bank=read_registry(registry)
    print(f"SWEEP targets={len(targets)} first={first} last={max_n} "
          f"attempts_per_N={attempts} deep_generations={deep_generations} "
          f"apply={apply} resume={resume}",flush=True)
    for index in range(state["next_index"],len(targets)):
        n=targets[index]
        work=base/f"n{n:04d}"
        if work.exists():
            # Partial run directory is safely reusable; stage files below
            # are checked and independently validated before reuse.
            if not resume:
                raise FileExistsError(f"Unexpected existing N folder: {work}")
        work.mkdir(parents=True,exist_ok=True)
        bank=read_registry(registry)
        old=float(bank["problems"][str(n)]["side"])
        # The previous N may have been solved in a dry-run and kept in
        # the preceding experiment's best_valid.json instead of bank.
        prior=None
        if index>0 and targets[index-1]==n-1:
            last=state["results"][-1]
            prior=last.get("best_file")
        source_file=None
        if prior:
            previous=_certified_file_or_none(prior,n-1)
            incumbent=_from_bank(bank,n-1)
            if previous.container_side<incumbent.container_side-1e-10:
                source_file=prior
        if index==0 and n==231:
            # User's already certified 900-generation local N230
            # record is available by default in its existing location.
            deep230=Path("results/kaggle_deep/n230_g900_s2300/best_valid.json")
            if deep230.exists():
                from_deep=_certified_file_or_none(deep230,230)
                from_bank=_from_bank(bank,230)
                if from_deep.container_side<from_bank.container_side-1e-10:
                    source_file=str(deep230)
        source_side=(float(load_packing_json(source_file)["side"])
                     if source_file else float(bank["problems"][str(n-1)]["side"]))
        print(f"\nBEGIN_SWEEP N={n} family_k={math.isqrt(n-1)} "
              f"founder_N={n-1} founder_L={source_side:.12f} "
              f"old_L={old:.12f}",flush=True)

        growth_report=work/"growth.json"
        growth_near=work/"near.npz"
        growth_best=work/"growth_best.json"
        if not growth_report.exists():
            # If interrupted after a partial write, start a fresh
            # numbered attempt instead of overwriting the evidence.
            if growth_near.exists() or growth_best.exists():
                count=1
                while (work/f"growth_retry_{count}.json").exists() or (
                       work/f"near_retry_{count}.npz").exists() or (
                       work/f"growth_best_retry_{count}.json").exists():
                    count+=1
                growth_report=work/f"growth_retry_{count}.json"
                growth_near=work/f"near_retry_{count}.npz"
                growth_best=work/f"growth_best_retry_{count}.json"
            grow(registry,n=n,attempts=attempts,iterations=iterations,
                 seed=seed+n,report=growth_report,checkpoint=growth_near,
                 best_file=growth_best,source_file=source_file,apply=False,
                 report_every=max(1,min(5,attempts)))
        growth_p=_certified_file_or_none(growth_best,n)
        chosen_file=growth_best if growth_p else None
        best=growth_p
        # Even if growth failed, the certified baseline N packing is
        # available to the independent deep stage, so the next N runs.
        if deep_generations:
            deep_folder=work/"deep"
            previous_deep=None
            if deep_folder.exists():
                progress=deep_folder/"progress.json"
                completed=(json.loads(progress.read_text(encoding="utf-8"))
                           if progress.exists() else {})
                if completed.get("finished_generation",0)<deep_generations:
                    previous_deep=deep_folder
                    count=1
                    while (work/f"deep_retry_{count}").exists():
                        count+=1
                    deep_folder=work/f"deep_retry_{count}"
            if not deep_folder.exists():
                prior_valid=(previous_deep/"best_valid.json"
                             if previous_deep else None)
                starter=(prior_valid if prior_valid and
                         _certified_file_or_none(prior_valid,n) else
                         growth_best if growth_p else None)
                optimize(registry=registry,n=n,
                         generations=deep_generations,iterations=deep_iterations,
                         seed=seed+100000+n,log_every=max(1,min(10,deep_generations)),
                         output_dir=deep_folder,candidate_file=starter,
                         shrink_max=.035,apply=False)
            deep_file=deep_folder/"best_valid.json"
            deep_p=_certified_file_or_none(deep_file,n)
            if deep_p and (best is None or deep_p.container_side<best.container_side-1e-10):
                best=deep_p
                chosen_file=deep_file
        accepted=False
        if best is not None and best.container_side<old-1e-10 and apply:
            offer=propose_improvement(
                registry,_packing_record(best),
                source="gerit_automatic_family_sweep",
                experiment_id=f"family-sweep-n{n}-seed{seed}",
                generation=deep_generations,operator="elastic_growth_deep")
            accepted=bool(offer["accepted"])
        # Keep the best certified saved pose (even for dry run), or
        # fall back to certified bank N. Never feed invalid states to N+1.
        current_bank=read_registry(registry)
        incumbent=_from_bank(current_bank,n)
        if best is None or incumbent.container_side<=best.container_side+1e-10:
            best=incumbent
            chosen_file=None
        result={"n":n,"old_side":old,"best_side":best.container_side,
                "best_file":str(chosen_file) if chosen_file else None,
                "source_file":source_file,"founder_side":source_side,
                "better":best.container_side<old-1e-10,
                "registered":accepted,
                "growth_certified":growth_p is not None}
        state["results"].append(result)
        state["next_index"]=index+1
        latest=read_registry(registry)
        state["projected_score"]=float(latest["total_score"])+math.fsum(
            (min(entry["best_side"],float(latest["problems"][str(entry["n"])]["side"]))
             -float(latest["problems"][str(entry["n"])]["side"]))/
            math.sqrt(entry["n"]) for entry in state["results"])
        _save_json(checkpoint,state)
        print(f"END_SWEEP N={n} best_L={best.container_side:.12f} "
              f"better={result['better']} applied={accepted} "
              f"projected_score={state['projected_score']:.12f} "
              f"completed={index+1}/{len(targets)}",flush=True)
    result={"completed":len(state["results"]),"improved":sum(
                item["better"] for item in state["results"]),
            "registered":sum(item["registered"] for item in state["results"]),
            "remaining":0,"score":read_registry(registry)["total_score"],
            "projected_score":state.get("projected_score")}
    print(f"FINISHED_SWEEP {result}",flush=True)
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--registry",default="results/kaggle_baseline/best_registry.json")
    p.add_argument("--output-dir",default="results/kaggle_auto/family_sweep_20261112")
    p.add_argument("--first",type=int,default=231)
    p.add_argument("--max-n",type=int,default=1000)
    p.add_argument("--attempts",type=int,default=10)
    p.add_argument("--iterations",type=int,default=250)
    p.add_argument("--deep-generations",type=int,default=10)
    p.add_argument("--deep-iterations",type=int,default=100)
    p.add_argument("--seed",type=int,default=20261112)
    p.add_argument("--apply",action="store_true")
    p.add_argument("--resume",action="store_true")
    a=p.parse_args()
    run(registry=a.registry,output_dir=a.output_dir,
        first=a.first,max_n=a.max_n,attempts=a.attempts,
        iterations=a.iterations,deep_generations=a.deep_generations,
        deep_iterations=a.deep_iterations,seed=a.seed,
        apply=a.apply,resume=a.resume)


if __name__=="__main__":
    main()
