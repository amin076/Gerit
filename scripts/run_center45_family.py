"""Verify and optionally register all fifteen four-corner/center-45 packings.

Usage:
  python scripts/run_center45_family.py --apply
  python scripts/run_center45_family.py --counts 5 17 37 --apply

No evolutionary generations, no archive reset, no Kaggle upload.
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
    sys.path.insert(0, str(ROOT))

from gerit.four_corner_center_45 import four_corner_center_45, SPECIAL_COUNTS
from gerit.kaggle import Candidate, validate as independent_validate
from scripts.kaggle_best_registry import read_registry, propose_improvement


def run_family(counts, registry, *, apply=False, report=None):
    counts = tuple(counts)
    if any(n not in SPECIAL_COUNTS for n in counts) or len(counts) != len(set(counts)):
        raise ValueError("Only unique N=4*m*m+1, 5<=N<=1000 are allowed")
    bank = read_registry(registry)
    rows = []
    for n in counts:
        previous = float(bank["problems"][str(n)]["side"])
        # Preserve the existing high-quality N=5 specialist.
        if n == 5:
            from experiments.five_squares.optimizer import best_inward_for_angle
            packing, _ = best_inward_for_angle(math.pi/4)
            family = "existing_n5_center45"
        else:
            packing = four_corner_center_45(n)
            family = "four_corner_center45"
        poses = tuple((repr(s.x),repr(s.y),repr(s.angle)) for s in packing.squares)
        verdict = independent_validate(
            Candidate(n, poses, family, packing.container_side))
        status = "invalid"
        message = verdict.reason
        if verdict.valid:
            status = "improvement_available" if packing.container_side < previous-1e-10 else "not_better"
        changed = False
        if verdict.valid and apply and status == "improvement_available":
            result = propose_improvement(
                registry,
                {"n":n, "side":packing.container_side,
                 "squares":[asdict(s) for s in packing.squares]},
                source="gerit_center45_family",
                experiment_id=f"four_corner_center45_m{math.isqrt((n-1)//4)}",
                generation=0, operator=family)
            changed = bool(result["accepted"])
            status = "updated" if changed else "not_better"
            bank = read_registry(registry)
        row = {"n":n,"m":math.isqrt((n-1)//4),
               "previous_side":previous, "candidate_side":packing.container_side,
               "current_side":float(bank["problems"][str(n)]["side"]),
               "valid":verdict.valid,"validator":message,
               "status":status, "updated":changed, "family":family}
        rows.append(row)
        print(f"N={n:3d} M={row['m']:2d} "
              f"before={previous:.12f} new={packing.container_side:.12f} "
              f"valid={verdict.valid} status={status}",flush=True)
    summary = {"family":"N=4*m*m+1 center45", "count":len(counts),
               "valid":sum(r["valid"] for r in rows),
               "updated":sum(r["updated"] for r in rows),
               "score":read_registry(registry)["total_score"],
               "results":rows}
    if report:
        path=Path(report)
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    print(f"FINISHED valid={summary['valid']}/{len(counts)} "
          f"updated={summary['updated']} score={summary['score']:.12f}",flush=True)
    return summary


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--counts",nargs="+",type=int,default=list(SPECIAL_COUNTS))
    p.add_argument("--registry",default="results/kaggle_baseline/best_registry.json")
    p.add_argument("--report",default="results/kaggle_center45_family/report.json")
    p.add_argument("--apply",action="store_true")
    args=p.parse_args()
    run_family(args.counts,args.registry,apply=args.apply,report=args.report)


if __name__=="__main__":
    main()
