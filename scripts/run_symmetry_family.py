"""Run one Gerit symmetry family, validate, archive and record provenance.

Each family has a dedicated launch script and shares this strict evaluator.
No hardcoded answers are injected; all changes are generated from the
specified structural family and checked by the independent interval SAT.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from gerit.kaggle import Candidate,validate as interval_validate
from gerit.symmetry_family_search import FAMILIES,search_family
from scripts.kaggle_best_registry import propose_improvement,read_registry
from scripts.kaggle_method_ledger import record_attempt,summarize_ledger

DEFAULT_COUNTS=(5,8,10,11,12,14,17,18,19,20)


def run_one(family,n,*,registry,ledger,output_dir,seed,iterations,
            release,report_every,apply):
    before=float(read_registry(registry)["problems"][str(n)]["side"])
    run_id=(f"family-{family}-n{n}-s{seed}-i{iterations}-r{release:g}")
    report_dir=Path(output_dir)
    report_dir.mkdir(parents=True,exist_ok=True)
    dest=report_dir/f"{run_id}.json"
    if dest.exists():
        raise FileExistsError(f"Refusing to overwrite historical report: {dest}")

    def progress(iteration,best,valid):
        print(f"FAMILY={family} N={n} STEP={iteration}/{iterations} "
              f"best_L={best.container_side:.12f} valid_trials={valid}",flush=True)

    result=search_family(n,family,seed=seed,iterations=iterations,
                         release=release,report_every=report_every,
                         progress=progress)
    best=result.best
    candidate=Candidate(n,tuple((repr(s.x),repr(s.y),repr(s.angle))
                                for s in best.squares),
                        f"gerit-{family}",best.container_side)
    verdict=interval_validate(candidate)
    accepted=False
    reason=verdict.reason
    if verdict.valid and apply and best.container_side < before-1e-10:
        try:
            change=propose_improvement(
                registry,
                {"n":n,"side":best.container_side,
                 "squares":[asdict(s) for s in best.squares]},
                source="gerit_symmetry_family_search",
                experiment_id=run_id,generation=iterations,
                operator=family)
            accepted=bool(change["accepted"])
        except ValueError as exc:
            reason=str(exc)
    current=float(read_registry(registry)["problems"][str(n)]["side"])
    metadata={
        "family":family, "script":f"scripts/run_{family}_family.py",
        "algorithm":"constrained_symmetry_geometry_refinement",
        "seed":seed,"parameters":{
            "iterations":iterations,"release":release,
            "report_every":report_every},
        "n":n,"previous_side":before,"candidate_side":best.container_side,
        "current_side":current,"valid":verdict.valid,
        "validation":reason,"accepted":accepted,
        "experiment_id":run_id,"valid_trials":result.valid_trials,
        "improvements":result.improvements,
        "initial_side":result.initial_side,
        "squares":[asdict(s) for s in best.squares],
    }
    dest.write_text(json.dumps(metadata,indent=2)+"\n",encoding="utf-8")
    record_attempt(
        ledger,n=n,family=family,
        script=metadata["script"],algorithm=metadata["algorithm"],
        seed=seed,parameters=metadata["parameters"],
        before_side=before,candidate_side=best.container_side,
        valid=verdict.valid,validation=reason,accepted=accepted,
        experiment_id=run_id,generation=iterations,
        note=f"Full packing and validation in {dest.as_posix()}")
    print(f"DONE FAMILY={family} N={n} L={best.container_side:.12f} "
          f"previous={before:.12f} valid={verdict.valid} "
          f"accepted={accepted} report={dest}",flush=True)
    return metadata


def main_for_family(family,argv=None):
    if family not in FAMILIES:
        raise ValueError(f"Unknown family: {family}")
    p=argparse.ArgumentParser(description=f"Gerit {family} family search")
    p.add_argument("--counts",nargs="+",type=int,default=list(DEFAULT_COUNTS))
    p.add_argument("--iterations",type=int,default=200)
    p.add_argument("--seed",type=int,default=20261112)
    p.add_argument("--release",type=float,default=.24)
    p.add_argument("--report-every",type=int,default=50)
    p.add_argument("--registry",default="results/kaggle_baseline/best_registry.json")
    p.add_argument("--ledger",default="results/kaggle_method_ledger.jsonl")
    p.add_argument("--output-dir",default="results/kaggle_family_reports")
    p.add_argument("--summary",default="results/kaggle_family_reports/method_summary.csv")
    p.add_argument("--apply",action="store_true",
                   help="Register only independently validated improvements")
    args=p.parse_args(argv)
    if (not args.counts or len(set(args.counts))!=len(args.counts)
            or any(not 2<=n<=1000 for n in args.counts)
            or args.iterations<0 or args.report_every<1
            or not math.isfinite(args.release) or not 0<=args.release<=2):
        p.error("Invalid counts or search parameters")
    records=[]
    for n in args.counts:
        records.append(run_one(
            family,n,registry=args.registry,ledger=args.ledger,
            output_dir=args.output_dir,seed=args.seed+n,
            iterations=args.iterations,release=args.release,
            report_every=args.report_every,apply=args.apply))
    summary=summarize_ledger(args.ledger,args.summary)
    print(f"FAMILY FINISHED name={family} cases={len(records)} "
          f"accepted={sum(r['accepted'] for r in records)} "
          f"ledger={args.ledger} summary={args.summary}",flush=True)
    return records


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("family",choices=FAMILIES)
    args,rest=p.parse_known_args()
    main_for_family(args.family,rest)
