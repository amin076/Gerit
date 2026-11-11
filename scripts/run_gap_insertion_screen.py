"""Screen the current Gerit registry for a free space to insert one square.

Unlike L-frame, insertion targets N+1 instead of a special N=k²+1
sequence. Dry-run (default) never changes the user's registry. A virtual
bank lets a newly found N+1 candidate serve as source for N+2. Only
independently certified and strictly better candidates may be saved.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import asdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from gerit.geometry import Packing,Square,validate_packing
from gerit.kaggle import Candidate,validate as interval_validate
from gerit.gap_insert_geometry import valid_one_more
from scripts.kaggle_best_registry import read_registry,propose_improvement
from scripts.kaggle_method_ledger import record_attempt,summarize_ledger

FAMILY="free_space_insert"
SCRIPT="scripts/run_gap_insertion_screen.py"


def screen(registry,*,apply=False,report=None,ledger=None,summary=None,
           max_n=1000,samples=500,seed=20261112,improved_only=True):
    if not 2<=max_n<=1000 or samples<1:
        raise ValueError("max_n=2..1000; samples >=1")
    if report and Path(report).exists():
        raise FileExistsError(f"Refusing to overwrite report: {report}")
    bank=read_registry(registry)
    virtual={}
    sides={n:float(bank["problems"][str(n)]["side"])
           for n in range(1,1001)}
    baseline={n:float(bank["problems"][str(n)]["baseline_side"])
              for n in range(1,1001)}
    initial_score=float(bank["total_score"])
    attempts=[]
    accepted=[]
    count_sources=0
    count_poses=0
    for n in range(1,max_n):
        if improved_only and sides[n]>=baseline[n]-1e-10:
            continue
        limit=sides[n+1]
        if limit<=sides[n]+1e-10:
            continue
        count_sources+=1
        row=virtual.get(n) or bank["problems"][str(n)]
        packing=Packing(tuple(Square(float(s["x"]),float(s["y"]),
                                     float(s["angle"])) for s in row["squares"]),
                        float(row["side"]))
        best,trials=valid_one_more(
            packing,limit,seed=seed+n,samples=samples)
        count_poses+=trials
        if best is None:
            print(f"NO_INSERT N={n}->{n+1} tested={trials} cap={limit:.8f}",
                  flush=True)
            continue
        fast=validate_packing(best,tolerance=0.0)
        cand=Candidate(n+1,tuple((repr(s.x),repr(s.y),repr(s.angle))
                                 for s in best.squares),
                       FAMILY,best.container_side)
        verdict=interval_validate(cand) if fast.valid else None
        certified=fast.valid and verdict.valid
        reason=(verdict.reason if verdict is not None
                else "strict SAT rejected")
        experiment_id=f"gap-insert-{n}-to-{n+1}-s{seed+n}-p{samples}"
        success=False
        if certified:
            if apply:
                try:
                    offer=propose_improvement(
                        registry,
                        {"n":n+1,"side":best.container_side,
                         "squares":[asdict(s) for s in best.squares]},
                        source="gerit_gap_insertion",
                        experiment_id=experiment_id,
                        generation=0,operator=FAMILY)
                    success=bool(offer["accepted"])
                except ValueError as exc:
                    reason=f"registry rejected: {exc}"
            else:
                success=True
            if success:
                virtual[n+1]={
                    "n":n+1,"side":best.container_side,
                    "squares":[asdict(s) for s in best.squares]}
                sides[n+1]=best.container_side
                accepted.append({"source_n":n,"target_n":n+1,
                                 "candidate_side":best.container_side})
        item={
            "source_n":n,"target_n":n+1,
            "previous_target_side":limit,
            "candidate_side":best.container_side,
            "valid":certified,"reason":reason,
            "accepted":success,"trials":trials,
            "experiment_id":experiment_id,
        }
        attempts.append(item)
        if ledger:
            record_attempt(
                ledger,n=n+1,family=FAMILY,script=SCRIPT,
                algorithm="free_space_angle_position_screen",
                seed=seed+n,
                parameters={"source_n":n,"samples":samples,
                            "max_n":max_n,"angles_deg":[0,15,30,45],
                            "dry_run":not apply},
                before_side=limit,candidate_side=best.container_side,
                valid=certified,validation=reason,
                accepted=apply and success,experiment_id=experiment_id,
                generation=0,
                note="Insert one square into inherited packing without moving others")
        print(f"{'UPDATED' if success and apply else 'WOULD_UPDATE' if success else 'REJECT'} "
              f"N={n}->{n+1} L={best.container_side:.12f} "
              f"before={limit:.12f} validated={certified}",flush=True)

    final_score=(float(read_registry(registry)["total_score"]) if apply else
                 math.fsum(sides[n]/math.sqrt(n)-1 for n in range(1,1001)))
    result={
        "family":FAMILY,"applied":apply,
        "source_count":count_sources,"evaluated_poses":count_poses,
        "accepted_count":len(accepted),
        "target_ns":[x["target_n"] for x in accepted],
        "initial_score":initial_score,"final_score":final_score,
        "accepted":accepted,"attempts":attempts,
        "warning":"Heuristic insertion search; absence of placements is NOT proof of optimality.",
    }
    if report:
        dst=Path(report)
        dst.parent.mkdir(parents=True,exist_ok=True)
        dst.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
        with dst.with_suffix(".csv").open("w",newline="",encoding="utf-8") as f:
            cols=["source_n","target_n","previous_target_side",
                  "candidate_side","valid","reason","accepted",
                  "trials","experiment_id"]
            writer=csv.DictWriter(f,fieldnames=cols)
            writer.writeheader()
            writer.writerows(attempts)
    if ledger and summary:
        summarize_ledger(ledger,summary)
    print(f"FINISHED sources={count_sources} poses={count_poses} "
          f"accepted={len(accepted)} targets={[x['target_n'] for x in accepted]} "
          f"score={final_score:.12f}",flush=True)
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--registry",default="results/kaggle_baseline/best_registry.json")
    p.add_argument("--report",default="results/kaggle_gap_insertion/screen.json")
    p.add_argument("--ledger",default="results/kaggle_method_ledger.jsonl")
    p.add_argument("--summary",default="results/kaggle_family_reports/method_summary.csv")
    p.add_argument("--max-n",type=int,default=1000)
    p.add_argument("--samples",type=int,default=500)
    p.add_argument("--seed",type=int,default=20261112)
    p.add_argument("--all-sources",action="store_true",
                   help="Screen unimproved sources too (slower)")
    p.add_argument("--apply",action="store_true")
    a=p.parse_args()
    screen(a.registry,apply=a.apply,report=a.report,ledger=a.ledger,
           summary=a.summary,max_n=a.max_n,samples=a.samples,
           seed=a.seed,improved_only=not a.all_sources)


if __name__=="__main__":
    main()
