"""Run N -> N+1 group rebuilding on Gerit's saved best solutions.

This search can relocate and rotate previously placed unit squares.
Dry run uses a virtual registry. Apply only certified improvements.
Method lineage (including moved group size and seed) is appended to ledger.
"""
from __future__ import annotations
import argparse,json,math,sys
from pathlib import Path
from dataclasses import asdict

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))

from gerit.geometry import Packing, Square, validate_packing
from gerit.kaggle import Candidate,validate as interval_validate
from gerit.group_rebuild_geometry import rebuild_with_extra
from scripts.kaggle_best_registry import read_registry,propose_improvement
from scripts.kaggle_method_ledger import record_attempt,summarize_ledger

SCRIPT="scripts/run_group_rebuild_screen.py"
FAMILY="group_rebuild_plus_one"


def run(registry,*,apply=False,report,ledger,summary,max_n=1000,
        attempts=60,probes=50,group_size=3,seed=20261112,
        all_sources=False,report_every=5):
    if not 2<=max_n<=1000 or attempts<1 or probes<1 or group_size<1:
        raise ValueError("Invalid search parameters")
    out=Path(report)
    if out.exists():raise FileExistsError(f"Refusing to overwrite report: {out}")
    bank=read_registry(registry)
    shadow={}
    sides={n:float(bank["problems"][str(n)]["side"]) for n in range(1,1001)}
    baseline={n:float(bank["problems"][str(n)]["baseline_side"])
              for n in range(1,1001)}
    previous_score=float(bank["total_score"])
    accepted=[]
    examined=0
    strict_valid=0
    considered=[]
    for n in range(max(1,group_size),max_n):
        if not all_sources and sides[n]>=baseline[n]-1e-10:continue
        if sides[n+1] <= sides[n]+1e-9:continue
        current=shadow.get(n) or bank["problems"][str(n)]
        source=Packing(tuple(Square(float(v["x"]),float(v["y"]),float(v["angle"]))
                             for v in current["squares"]),float(current["side"]))
        examined+=1
        candidate,stats=rebuild_with_extra(
            source,sides[n+1],seed=seed+n,attempts=attempts,
            group_size=group_size,probes=probes)
        strict_valid+=stats["strict_valid"]
        previous=sides[n+1]
        if candidate is None:
            if examined%report_every==0:
                print(f"SCREENED {examined} source={n} no candidate",flush=True)
            continue
        geometry_valid=validate_packing(candidate,tolerance=0.0).valid
        verdict=interval_validate(Candidate(
            n+1,tuple((repr(s.x),repr(s.y),repr(s.angle))
                      for s in candidate.squares),FAMILY,candidate.container_side
        )) if geometry_valid else None
        certified=bool(verdict and verdict.valid)
        reason=verdict.reason if verdict else "strict SAT failed"
        success=False
        experiment_id=f"group-rebuild-n{n}-to-{n+1}-s{seed+n}-a{attempts}-k{group_size}"
        if certified and candidate.container_side<previous-1e-10:
            if apply:
                try:
                    update=propose_improvement(
                        registry,{"n":n+1,"side":candidate.container_side,
                                  "squares":[asdict(s) for s in candidate.squares]},
                        source="gerit_group_rebuild",
                        experiment_id=experiment_id,generation=0,
                        operator=FAMILY)
                    success=bool(update["accepted"])
                except ValueError as exc:
                    reason=f"registry validation failed: {exc}"
            else:
                success=True
            if success:
                sides[n+1]=candidate.container_side
                shadow[n+1]={"n":n+1,"side":candidate.container_side,
                             "squares":[asdict(s) for s in candidate.squares]}
                accepted.append({"from_n":n,"to_n":n+1,"previous_side":previous,
                                 "new_side":candidate.container_side})
        entry={"from_n":n,"to_n":n+1,"candidate_side":candidate.container_side,
               "previous_side":previous,"certified":certified,
               "accepted":success,"reason":reason,"search":stats,
               "experiment_id":experiment_id}
        considered.append(entry)
        if ledger:
            record_attempt(
                ledger,n=n+1,family=FAMILY,script=SCRIPT,
                algorithm="rebuild_k_of_n_squares_plus_one",
                seed=seed+n,parameters={"attempts":attempts,"probes":probes,
                    "group_size":group_size,"source_n":n,
                    "all_sources":all_sources,"dry_run":not apply},
                before_side=previous,candidate_side=candidate.container_side,
                valid=certified,validation=reason,
                accepted=success and apply,experiment_id=experiment_id,
                note="Partial geometry rebuild with free x/y and square angles")
        print(f"{'UPDATED' if apply and success else 'WOULD_UPDATE' if success else 'REJECT'} "
              f"N={n}->{n+1} old={previous:.10f} "
              f"new={candidate.container_side:.10f} certified={certified}",
              flush=True)
    score=(float(read_registry(registry)["total_score"]) if apply else
           math.fsum(sides[n]/math.sqrt(n)-1 for n in range(1,1001)))
    result={"family":FAMILY,"applied":apply,"sources_screened":examined,
            "strict_valid_trials":strict_valid,"accepted_count":len(accepted),
            "accepted":accepted,"certified_candidates":sum(x["certified"] for x in considered),
            "initial_score":previous_score,"final_score":score,
            "attempts":considered,
            "note":"No result is a proof of optimality. Only full independent SAT can enter registry."}
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    if ledger and summary:summarize_ledger(ledger,summary)
    print(f"FINISHED sources={examined} valid_trials={strict_valid} "
          f"accepted={len(accepted)} score={score:.12f}",flush=True)
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--registry",default="results/kaggle_baseline/best_registry.json")
    p.add_argument("--report",default="results/kaggle_group_rebuild/dryrun.json")
    p.add_argument("--ledger",default="results/kaggle_method_ledger.jsonl")
    p.add_argument("--summary",default="results/kaggle_family_reports/method_summary.csv")
    p.add_argument("--max-n",type=int,default=120)
    p.add_argument("--attempts",type=int,default=60)
    p.add_argument("--probes",type=int,default=50)
    p.add_argument("--group-size",type=int,default=3)
    p.add_argument("--seed",type=int,default=20261112)
    p.add_argument("--report-every",type=int,default=5)
    p.add_argument("--all-sources",action="store_true")
    p.add_argument("--apply",action="store_true")
    a=p.parse_args()
    run(a.registry,apply=a.apply,report=a.report,ledger=a.ledger,
        summary=a.summary,max_n=a.max_n,attempts=a.attempts,
        probes=a.probes,group_size=a.group_size,seed=a.seed,
        all_sources=a.all_sources,report_every=a.report_every)


if __name__=="__main__":main()
