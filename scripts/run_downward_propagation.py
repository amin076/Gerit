"""Propagate a strong N-square packing down to smaller problems by deletion.

Mathematically, any valid unit-square packing of N remains valid after
deleting squares. Deleting chosen boundary squares can also reduce the
tight envelope. This screening NEVER moves squares or compromises the
existing archive; each candidate is validated independently before apply.

Accepts either the saved best registry at --source-n or a dry-run
best_valid.json produced by scripts/run_deep_elastic.py.
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

from gerit.geometry import Packing,Square,minimum_bounding_square,validate_packing
from gerit.kaggle import Candidate,validate as independent_validate
from scripts.kaggle_best_registry import read_registry,propose_improvement

FAMILY="validated_downward_deletion"


def _packing(item):
    return Packing(tuple(
        Square(float(s["x"]),float(s["y"]),float(s["angle"]))
        for s in item["squares"]),float(item["side"]))


def _measure(p):
    p=minimum_bounding_square(p.squares)
    if not validate_packing(p,tolerance=0.).valid:
        raise ValueError("Invalid source packing")
    result=independent_validate(Candidate(
        len(p.squares),tuple((repr(s.x),repr(s.y),repr(s.angle))
                             for s in p.squares),FAMILY,p.container_side))
    if not result.valid:
        raise ValueError(f"Independent certification rejected: {result.reason}")
    return p


def _delete_one(p):
    """Choose removal yielding smallest true bounding square."""
    squares=p.squares
    best=None
    best_index=-1
    for i in range(len(squares)):
        proposal=minimum_bounding_square(squares[:i]+squares[i+1:])
        if best is None or proposal.container_side<best.container_side-1e-12:
            best,best_index=proposal,i
    return best,best_index


def run(*,registry,source_n=230,min_n=226,
        candidate_file=None,report=None,apply=False):
    if not 2<=min_n<source_n<=1000:
        raise ValueError("Expected 2<=min_n<source_n<=1000")
    if report and Path(report).exists():
        raise FileExistsError(f"Refusing to overwrite existing report: {report}")
    bank=read_registry(registry)
    original_score=float(bank["total_score"])
    if candidate_file:
        item=json.loads(Path(candidate_file).read_text(encoding="utf-8"))
        if int(item["n"])!=source_n:
            raise ValueError("Candidate file N does not match source-n")
    else:
        item=bank["problems"][str(source_n)]
    source=_measure(_packing(item))
    sides={n:float(bank["problems"][str(n)]["side"])
           for n in range(1,1001)}
    # The file's source might not yet have been registered, but this
    # propagation does not modify the source-N registry entry.
    results=[]
    improvements=[]
    current=source
    for n in range(source_n-1,min_n-1,-1):
        current,removed_index=_delete_one(current)
        old=sides[n]
        is_better=current.container_side<old-1e-10
        certified=False
        reason="not an improvement"
        updated=False
        if is_better:
            checked=independent_validate(Candidate(
                n,tuple((repr(s.x),repr(s.y),repr(s.angle))
                         for s in current.squares),
                FAMILY,current.container_side))
            certified=checked.valid and validate_packing(current,tolerance=0.).valid
            reason=checked.reason
            if certified:
                if apply:
                    offer=propose_improvement(
                        registry,{"n":n,"side":current.container_side,
                                  "squares":[asdict(s) for s in current.squares]},
                        source="gerit_downward_deletion",
                        experiment_id=f"downward-from-{source_n}-to-{n}",
                        generation=0,operator=FAMILY)
                    updated=bool(offer["accepted"])
                else:
                    updated=True
                if updated:
                    sides[n]=current.container_side
                    improvements.append({
                        "n":n,"previous_side":old,
                        "new_side":current.container_side,
                        "removed_square_index":removed_index})
        result={"n":n,"previous_side":old,
                "candidate_side":current.container_side,
                "removed_square_index":removed_index,
                "certified":certified,"accepted":updated,
                "reason":reason}
        results.append(result)
        print(f"{'UPDATED' if apply and updated else 'WOULD_UPDATE' if updated else 'UNCHANGED'} "
              f"N={n} previous={old:.12f} "
              f"candidate={current.container_side:.12f} valid={certified}",
              flush=True)
    final=(float(read_registry(registry)["total_score"]) if apply else
           math.fsum(sides[n]/math.sqrt(n)-1 for n in range(1,1001)))
    report_data={"source_n":source_n,"source_side":source.container_side,
                 "source_candidate_file":str(candidate_file) if candidate_file else None,
                 "min_n":min_n,"applied":apply,
                 "improvements":improvements,"results":results,
                 "initial_score":original_score,"final_score":final,
                 "warning":"Source N itself is not registered by this script."}
    if report:
        output=Path(report)
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(report_data,indent=2)+"\n",encoding="utf-8")
    print(f"FINISHED improved={len(improvements)} "
          f"targets={[r['n'] for r in improvements]} score={final:.12f}",
          flush=True)
    return report_data


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--registry",default="results/kaggle_baseline/best_registry.json")
    parser.add_argument("--source-n",type=int,default=230)
    parser.add_argument("--min-n",type=int,default=226)
    parser.add_argument("--candidate-file")
    parser.add_argument("--report",default="results/kaggle_deep/downward_dryrun.json")
    parser.add_argument("--apply",action="store_true")
    args=parser.parse_args()
    run(registry=args.registry,source_n=args.source_n,min_n=args.min_n,
        candidate_file=args.candidate_file,report=args.report,apply=args.apply)


if __name__=="__main__":
    main()
