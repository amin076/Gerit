"""Audit and optionally register certified winners from a finished family sweep.

The automated sweep defaults to dry-run. This tool reads its durable
sweep_state.json, rechecks *every* proposed winning packing using strict
geometry SAT and the independent interval SAT validator, then offers
only strictly better solutions to the existing best-answer registry.

Default mode is dry-run audit, no bank mutation. --apply performs a
second validation by propose_improvement before each bank update.

Never re-runs hundreds of optimization generations. The source sweep
directory and its best-file artifacts remain unchanged.
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
from scripts.run_deep_elastic import _packing_from_record,_packing_record,_certify


def _atomic_report(path, payload):
    p=Path(path)
    if p.exists():
        raise FileExistsError(f"Refusing to overwrite report: {p}")
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("x",encoding="utf-8") as f:
        json.dump(payload,f,indent=2,allow_nan=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())


def _locate(path,root):
    p=Path(path)
    if p.is_file():
        return p
    # A sweep may have been run from a project root with a relative
    # path and subsequently inspected from a different current folder.
    candidates=[root/p, root.parent/p, root.parent.parent/p,
                root.parent.parent.parent/p]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Candidate packing file missing: {path}")


def audit(*,registry,sweep_dir,apply=False,report=None):
    root=Path(sweep_dir)
    state_path=root/"sweep_state.json"
    state=json.loads(state_path.read_text(encoding="utf-8"))
    rows=state["results"]
    if len(rows)!=state.get("next_index"):
        raise ValueError("Sweep state result count and checkpoint index disagree")
    if len({int(row["n"]) for row in rows})!=len(rows):
        raise ValueError("Duplicate N values in campaign state")
    if report is not None and Path(report).exists():
        raise FileExistsError(f"Refusing to overwrite report: {report}")
    bank=read_registry(registry)
    initial_score=float(bank["total_score"])
    validated=[]
    notes=[]
    # All candidates are verified before any change to the registry.
    for row in rows:
        n=int(row["n"])
        side=float(bank["problems"][str(n)]["side"])
        path=row.get("best_file")
        if not path:
            if float(row["best_side"])<side-1e-10:
                raise ValueError(
                    f"Missing certified candidate file for improved N={n}")
            continue
        try:
            candidate=load_packing_json(_locate(path,root))
            if int(candidate["n"])!=n or len(candidate["squares"])!=n:
                raise ValueError("Candidate N/count inconsistent")
            p=_packing_from_record(candidate)
            ok,reason=_certify(p)
            if not ok:
                raise ValueError(f"Independent SAT rejected: {reason}")
            if not math.isclose(p.container_side,float(row["best_side"]),
                                abs_tol=1e-8,rel_tol=0.):
                raise ValueError("Stored best side differs from campaign log")
            if p.container_side<side-1e-10:
                validated.append((n,p,str(path)))
            else:
                notes.append({"n":n,"status":"already_in_bank_or_not_better",
                              "candidate_side":p.container_side,"bank_side":side})
        except (ValueError,FileNotFoundError,KeyError,TypeError) as e:
            # Reject the entire apply operation if any evidence is
            # missing, inconsistent or invalid, rather than partially
            # updating and silently skipping bad answers.
            raise ValueError(f"Campaign audit failed at N={n}, file={path}: {e}") from e
    projected=initial_score+math.fsum(
        (p.container_side-float(bank["problems"][str(n)]["side"]))/math.sqrt(n)
        for n,p,_ in validated)
    print(f"AUDIT completed={len(rows)} verified_better={len(validated)} "
          f"initial_score={initial_score:.12f} "
          f"projected_score={projected:.12f} apply={apply}",flush=True)
    updates=[]
    for n,p,source in validated:
        old=float(bank["problems"][str(n)]["side"])
        accepted=False
        if apply:
            outcome=propose_improvement(
                registry,_packing_record(p),
                source="gerit_auto_sweep_certified_promotion",
                experiment_id=f"auto-sweep-promotion-n{n}-from-{root.name}",
                generation=0,operator="audited_sweep_promotion")
            accepted=bool(outcome["accepted"])
        updates.append({"n":n,"previous_side":old,
                        "candidate_side":p.container_side,
                        "candidate_file":source,
                        "registered":accepted})
        print(f"{'UPDATED' if accepted else 'VERIFIED'} N={n} "
              f"L={p.container_side:.12f} previous={old:.12f}",flush=True)
    final=float(read_registry(registry)["total_score"])
    result={"sweep_dir":str(root),"completed":len(rows),
            "verified_better":len(validated),
            "registered":sum(x["registered"] for x in updates),
            "applied":bool(apply),"initial_score":initial_score,
            "projected_score":projected,"current_score":final,
            "updates":updates,"notes":notes}
    if report:
        _atomic_report(report,result)
    print(f"FINISHED_PROMOTION verified={len(validated)} "
          f"registered={result['registered']} "
          f"current_score={final:.12f} "
          f"projected_score={projected:.12f}",flush=True)
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--registry",default="results/kaggle_baseline/best_registry.json")
    parser.add_argument("--sweep-dir",default="results/kaggle_auto/full231_1000")
    parser.add_argument("--report",default="results/kaggle_auto/full231_1000_audit.json")
    parser.add_argument("--apply",action="store_true")
    args=parser.parse_args()
    audit(registry=args.registry,sweep_dir=args.sweep_dir,
          apply=args.apply,report=args.report)


if __name__=="__main__":
    main()
