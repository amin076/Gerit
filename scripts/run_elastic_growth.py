"""Grow and relax whole unit-square packings across consecutive N.

Default pilot starts from saved N=226 and tries N=227. Optionally continue
into 228/229, using valid winners as founders. Dry-run never edits bank.
Only strict-SAT AND independent interval-SAT approved candidates may be
offered to the 1000-case registry. Original Gerit engine is untouched.
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

from gerit.geometry import Packing,Square
from gerit.elastic_growth import initial_growth_pose,relax_once,certified_candidate
from gerit.kaggle import Candidate,validate as interval_validate
from scripts.kaggle_best_registry import read_registry,propose_improvement
from scripts.kaggle_method_ledger import record_attempt,summarize_ledger

FAMILY="elastic_collective_growth"
SCRIPT="scripts/run_elastic_growth.py"


def _from_record(entry):
    return Packing(tuple(
        Square(float(s["x"]),float(s["y"]),float(s["angle"]))
        for s in entry["squares"]),float(entry["side"]))


def _independent(n,packing):
    return interval_validate(Candidate(
        n,tuple((repr(s.x),repr(s.y),repr(s.angle))
                for s in packing.squares),
        FAMILY,packing.container_side))


def run(*,registry,first=227,last=227,attempts=16,
        iterations=400,seed=100,cap_margin=.001,
        randomize_count=0,apply=False,report=None,
        ledger=None,summary=None,report_every=5):
    if not 2<=first<=last<=1000:
        raise ValueError("Counts must satisfy 2 <= first <= last <= 1000")
    if attempts<1 or iterations<1 or report_every<1 or not 0<cap_margin<.1:
        raise ValueError("Invalid search budget or cap margin")
    if report is not None and Path(report).exists():
        raise FileExistsError(f"Refusing to replace report: {report}")
    bank=read_registry(registry)
    sides={n:float(bank["problems"][str(n)]["side"]) for n in range(1,1001)}
    initial_score=float(bank["total_score"])
    virtual={}
    outcomes=[]
    improvements=[]
    # Persistent deterministic RNG sequence across attempts, enabling
    # exact replay by seed and experiment parameters.
    rng=np.random.default_rng(seed)
    for n in range(first,last+1):
        current=sides[n]
        cap=min(current-cap_margin, math.isqrt(n-1)+1-cap_margin)
        source=virtual.get(n-1) or _from_record(bank["problems"][str(n-1)])
        print(f"BEGIN target_N={n} source_N={n-1} "
              f"source_L={source.container_side:.12f} "
              f"current_L={current:.12f} cap={cap:.12f}",flush=True)
        if cap<=math.sqrt(n)+1e-6:
            outcomes.append({"n":n,"accepted":False,
                             "reason":"cap below area lower bound"})
            continue
        best=None
        stats={"n":n,"source_n":n-1,"seed":seed,
               "attempts":attempts,"strict_valid":0,"interval_valid":0,
               "lowest_energy":None,"accepted":False,
               "previous_side":current,"target_cap":cap}
        for attempt in range(attempts):
            poses=initial_growth_pose(source,rng,cap,
                                      randomize_count=randomize_count)
            solution,loss,used=relax_once(
                poses,cap,iterations=iterations)
            stats["lowest_energy"]=(loss if stats["lowest_energy"] is None
                                      else min(stats["lowest_energy"],loss))
            check=certified_candidate(solution,cap)
            reason="no strict collision-free packing"
            if check:
                stats["strict_valid"]+=1
                verdict=_independent(n,check)
                reason=verdict.reason
                if verdict.valid:
                    stats["interval_valid"]+=1
                    if best is None or check.container_side<best.container_side:
                        best=check
                        print(f"CERTIFIED attempt={attempt+1}/{attempts} "
                              f"N={n} L={check.container_side:.12f} "
                              f"old={current:.12f}",flush=True)
            if (attempt+1)%report_every==0 or attempt+1==attempts:
                print(f"TRIAL {attempt+1}/{attempts} N={n} "
                      f"energy={loss:.9g} valid={bool(check)} "
                      f"certified={stats['interval_valid']} "
                      f"best_L={(best.container_side if best else float('nan')):.12f}",
                      flush=True)
        if best is not None:
            experiment_id=(f"elastic-growth-n{n}-seed{seed}-"
                           f"a{attempts}-iter{iterations}")
            if apply:
                try:
                    result=propose_improvement(
                        registry,
                        {"n":n,"side":best.container_side,
                         "squares":[asdict(s) for s in best.squares]},
                        source="gerit_collective_elastic_relaxation",
                        experiment_id=experiment_id,
                        generation=attempts,
                        operator=FAMILY)
                    accepted=bool(result["accepted"])
                except ValueError as exc:
                    accepted=False
                    stats["registry_rejection"]=str(exc)
            else:
                accepted=True
            if accepted:
                virtual[n]=best
                sides[n]=best.container_side
                improvements.append({"n":n,"previous_side":current,
                                     "new_side":best.container_side,
                                     "source_n":n-1,
                                     "source_side":source.container_side})
                print(f"{'UPDATED' if apply else 'WOULD_UPDATE'} "
                      f"N={n} old={current:.12f} "
                      f"new={best.container_side:.12f}",flush=True)
            if ledger:
                record_attempt(
                    ledger,n=n,family=FAMILY,script=SCRIPT,
                    algorithm="all_square_sat_penalty_coordinate_and_rotation",
                    seed=seed,parameters={
                        "source_n":n-1,"attempts":attempts,
                        "iterations":iterations,"randomize_count":randomize_count,
                        "cap_margin":cap_margin,"angles_free":True,
                        "temporary_overlap":True,"dry_run":not apply,
                    },before_side=current,candidate_side=best.container_side,
                    valid=True,validation="strict SAT plus independent interval SAT",
                    accepted=apply and accepted,experiment_id=experiment_id,
                    generation=attempts,
                    note="N+1 growth; all old square coordinates and rotations free")
        stats["accepted"]=bool(best is not None and sides[n]<current)
        stats["best_side"]=best.container_side if best else None
        outcomes.append(stats)
    final=(float(read_registry(registry)["total_score"]) if apply else
           math.fsum(sides[n]/math.sqrt(n)-1 for n in range(1,1001)))
    result={"family":FAMILY,"applied":apply,"first":first,"last":last,
            "initial_score":initial_score,"final_score":final,
            "accepted_count":len(improvements),"improvements":improvements,
            "outcomes":outcomes,
            "warning":"Temporary overlaps are only optimizer states; only independently verified solutions may enter the registry."}
    if report:
        file=Path(report)
        file.parent.mkdir(parents=True,exist_ok=True)
        file.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    if ledger and summary:
        summarize_ledger(ledger,summary)
    print(f"FINISHED accepted={len(improvements)} "
          f"targets={[x['n'] for x in improvements]} score={final:.12f}",
          flush=True)
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--registry",default="results/kaggle_baseline/best_registry.json")
    p.add_argument("--first",type=int,default=227)
    p.add_argument("--last",type=int,default=227)
    p.add_argument("--attempts",type=int,default=16)
    p.add_argument("--iterations",type=int,default=400)
    p.add_argument("--seed",type=int,default=100)
    p.add_argument("--cap-margin",type=float,default=.001)
    p.add_argument("--randomize-count",type=int,default=0)
    p.add_argument("--report-every",type=int,default=5)
    p.add_argument("--report",default="results/kaggle_elastic_growth/n227_dryrun.json")
    p.add_argument("--ledger",default="results/kaggle_method_ledger.jsonl")
    p.add_argument("--summary",default="results/kaggle_family_reports/method_summary.csv")
    p.add_argument("--apply",action="store_true")
    a=p.parse_args()
    run(registry=a.registry,first=a.first,last=a.last,
        attempts=a.attempts,iterations=a.iterations,
        seed=a.seed,cap_margin=a.cap_margin,
        randomize_count=a.randomize_count,apply=a.apply,
        report=a.report,ledger=a.ledger,summary=a.summary,
        report_every=a.report_every)


if __name__=="__main__":
    main()
