"""Export the CURRENT best-answer registry, not a stale run-history scan.

Builds the complete 500,500-row competition CSV. Reimports it and checks
every chosen improvement using independent interval geometry validation.
Does not submit to Kaggle or change the registry.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from gerit.kaggle import Candidate, export, reimport, validate
from scripts.kaggle_best_registry import read_registry


def build(registry, output):
    bank=read_registry(registry)
    candidates={}
    expected={}
    for n in range(1,1001):
        entry=bank["problems"][str(n)]
        if len(entry["squares"]) != n:
            raise ValueError(f"Registry N={n}: incorrect square count")
        side=float(entry["side"])
        baseline=float(entry.get("baseline_side",math.isqrt(n-1)+1))
        if side < baseline-1e-10:
            candidate=Candidate(
                n,tuple((repr(float(s["x"])),repr(float(s["y"])),
                         repr(float(s["angle"]))) for s in entry["squares"]),
                "gerit_best_registry",side)
            verified=validate(candidate)
            if not verified.valid:
                raise ValueError(f"Registry N={n} rejected: {verified.reason}")
            candidates[n]=candidate
            expected[n]=side
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing submission: {output}")
    tmp=output.with_suffix(output.suffix+".building")
    try:
        count=export(tmp,candidates,complete=True)
        if count!=500500:
            raise ValueError(f"Expected 500500 rows, got {count}")
        imported=reimport(tmp)
        if len(imported)!=1000:
            raise ValueError(f"Expected 1000 puzzles, got {len(imported)}")
        for n,side in expected.items():
            parsed=imported[n]
            checked=validate(parsed)
            if not checked.valid or abs(checked.side-side)>max(1e-8,2e-10*side):
                raise ValueError(f"CSV round-trip N={n} mismatch: {checked}")
        tmp.replace(output)
    finally:
        tmp.unlink(missing_ok=True)
    total=math.fsum(
        ((expected[n] if n in expected else math.isqrt(n-1)+1)
         /math.sqrt(n)-1) for n in range(1,1001))
    result={
        "output":str(output),"rows":count,"puzzles":1000,
        "improved_puzzles":len(expected),
        "selected_improvements":sorted(expected),
        "projected_score":total,
        "registry_score":bank["total_score"],
        "matches_registry":abs(total-float(bank["total_score"]))<1e-8,
        "submitted":False,
    }
    if not result["matches_registry"]:
        output.unlink(missing_ok=True)
        raise ValueError("Output projected score differs from current registry score")
    print(json.dumps(result,indent=2))
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--registry",default="results/kaggle_baseline/best_registry.json")
    p.add_argument("--output",default="kaggle_output/gerit_registry_submission.csv")
    args=p.parse_args()
    build(args.registry,args.output)


if __name__=="__main__":
    main()
