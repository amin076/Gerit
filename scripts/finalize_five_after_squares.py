"""Audit/promote all ten completed five-after-square family sweeps, then export Kaggle CSV.

Default: read-only preflight and aggregate score projection.
--apply: independently certify every winner first, then register strictly
improving packings and export the official-schema 500,500-row CSV.

No optimizer reruns. No new experiments. Existing bank is preserved in
read-only mode; updates use the existing atomic per-problem registry writer.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from scripts.promote_auto_sweep import audit
from scripts.kaggle_best_registry import read_registry
from scripts.export_registry_submission import build


def execute(*, root, registry, apply=False, output=None):
    root=Path(root)
    registry=Path(registry)
    groups=[]
    # Preflight ALL ten before the first registry change.
    for k in range(22,32):
        lo=k*k+1
        folder=root/f"k{k:02d}_n{lo}_{lo+4}"
        state=folder/"sweep_state.json"
        if not state.is_file():
            raise FileNotFoundError(f"Missing group checkpoint: {state}")
        raw=json.loads(state.read_text(encoding="utf-8"))
        if raw.get("next_index")!=5 or len(raw.get("results",[]))!=5:
            raise ValueError(f"Unfinished group: {folder}")
        groups.append(folder)

    original=float(read_registry(registry)["total_score"])
    preflight=[]
    for folder in groups:
        preflight.append(audit(registry=registry,sweep_dir=folder,apply=False,report=None))
    projected=original+sum(r["projected_score"]-original for r in preflight)
    print(f"ALL_GROUPS_PREFLIGHT families={len(groups)} "
          f"winners={sum(x['verified_better'] for x in preflight)} "
          f"registry_score={original:.12f} projected_score={projected:.12f}",
          flush=True)
    if not apply:
        print("DRY_RUN bank_unchanged=True; add --apply to register and export",
              flush=True)
        return {"projected_score":projected,"applied":False}
    if output is None:
        raise ValueError("An explicit --output is required for --apply")
    output=Path(output)
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite submission CSV: {output}")
    applied=[]
    for folder in groups:
        applied.append(audit(registry=registry,sweep_dir=folder,apply=True,report=None))
    updated=float(read_registry(registry)["total_score"])
    print(f"ALL_GROUPS_REGISTERED accepted={sum(x['registered'] for x in applied)} "
          f"score={updated:.12f}",flush=True)
    exported=build(registry,output)
    return {"applied":True,"accepted":sum(x["registered"] for x in applied),
            "score":updated,"export":exported}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",default="results/kaggle_auto/five_after_squares_k22_31")
    p.add_argument("--registry",default="results/kaggle_baseline/best_registry.json")
    p.add_argument("--apply",action="store_true")
    p.add_argument("--output",default="kaggle_output/gerit_50_cases_submission.csv")
    args=p.parse_args()
    execute(root=args.root,registry=args.registry,apply=args.apply,
            output=args.output)


if __name__=="__main__":
    main()
