"""Record source metadata of existing 1000-answer winners in method ledger.

Uses ONLY provenance stored in the registry; unknown seed/parameters remain
unknown. Does not modify the registry or claim a winning pose was generated
by any new family script.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from scripts.kaggle_best_registry import read_registry
from scripts.kaggle_method_ledger import record_attempt,summarize_ledger


def backfill(registry,ledger,summary):
    bank=read_registry(registry)
    path=Path(ledger)
    existing=set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row=json.loads(line)
                if row.get("note")=="historical registry winner":
                    existing.add((row["n"],row["experiment_id"],row["candidate_side"]))
    count=0
    for n in range(1,1001):
        row=bank["problems"][str(n)]
        source=row.get("source","grid-baseline")
        if source=="grid-baseline" or (row["side"] >= row.get("baseline_side",row["side"])-1e-10):
            continue
        experiment_id=row.get("experiment_id","unrecorded")
        key=(n,experiment_id,row["side"])
        if key in existing:
            continue
        operator=row.get("operator","unknown")
        script=(
            "scripts/run_center45_family.py"
            if source=="gerit_center45_family"
            else "scripts/audit_kaggle_symmetry.py"
            if source=="gerit_symmetry_preflight"
            else "historical source: "+source)
        record_attempt(
            ledger,n=n,family=operator,script=script,
            algorithm=source,seed=None,parameters={"historical":True},
            before_side=row.get("previous_best_side",row["baseline_side"]),
            candidate_side=row["side"],valid=True,
            validation=row.get("validation",{}).get("method","recorded in registry"),
            accepted=True,experiment_id=experiment_id,
            generation=row.get("generation",0),
            note="historical registry winner")
        count+=1
    groups=summarize_ledger(ledger,summary)
    print(f"BACKFILL added={count} families={len(groups)} ledger={ledger}",flush=True)
    return count


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--registry",default="results/kaggle_baseline/best_registry.json")
    p.add_argument("--ledger",default="results/kaggle_method_ledger.jsonl")
    p.add_argument("--summary",default="results/kaggle_family_reports/method_summary.csv")
    args=p.parse_args()
    backfill(args.registry,args.ledger,args.summary)


if __name__=="__main__":
    main()
