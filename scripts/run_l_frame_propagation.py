"""Propagate L-frame geometry across all 1000 archived problems.

Dry-run by default, with a virtual evolving bank so multi-generation
L-chain opportunities are still found. With --apply, accepted improvements
are inserted using Gerit's strict and independent interval validators.
The append-only method ledger records the source and target of each offer.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gerit.geometry import Packing, Square, minimum_bounding_square, validate_packing
from gerit.kaggle import Candidate, validate as interval_validate
from gerit.l_frame_geometry import l_frame_extend, l_frame_target, SPECIAL_30
from scripts.kaggle_best_registry import read_registry, propose_improvement
from scripts.kaggle_method_ledger import record_attempt, summarize_ledger

SCRIPT = "scripts/run_l_frame_propagation.py"
FAMILY = "l_frame_recursive"


def _to_packing(entry) -> Packing:
    p = Packing(tuple(Square(float(s["x"]), float(s["y"]), float(s["angle"]))
                      for s in entry["squares"]), float(entry["side"]))
    return p


def _certify(n, packing):
    if len(packing.squares) != n:
        return False, "incorrect number of squares"
    fast = validate_packing(packing, tolerance=0)
    if not fast.valid:
        return False, f"strict SAT: {fast}"
    check = interval_validate(Candidate(
        n, tuple((repr(s.x), repr(s.y), repr(s.angle))
                 for s in packing.squares),
        FAMILY, packing.container_side))
    return check.valid, check.reason


def propagate(registry, *, apply=False, report=None, ledger=None,
              summary_csv=None, max_n=1000):
    if not 2 <= max_n <= 1000:
        raise ValueError("max_n must be between 2 and 1000")
    bank = read_registry(registry)
    # Lightweight virtual bank stores only accepted replacement packings.
    # All sources are read from the current registry unless improved in
    # this run; once improved, the new target can serve as a source.
    shadow = {}
    lineage = {}
    initial_sides = {n:float(bank["problems"][str(n)]["side"])
                     for n in range(1,max_n+1)}
    current_sides = dict(initial_sides)
    efforts = 0
    eligible = 0
    valid = 0
    accepted = 0
    failures = []
    rows = []
    transitions = []

    for n in range(1,max_n+1):
        efforts += 1
        entry = shadow.get(n) or bank["problems"][str(n)]
        old_side = current_sides[n]
        target = l_frame_target(n, old_side, limit=max_n)
        if target is None:
            continue
        # Predicted enclosing side, before constructing geometry. There
        # can be small numeric roundoff; the rigorous check is below.
        predicted = old_side + 1.0
        if predicted >= current_sides[target] - 1e-9:
            continue
        eligible += 1
        packing = _to_packing(entry)
        # The saved source is trusted only after the complete extension
        # is independently validated, including all inherited squares.
        candidate = l_frame_extend(packing)
        actual_target = len(candidate.squares)
        if actual_target != target:
            failures.append({"source":n,"target":target,
                             "reason":f"wrong target count: {actual_target}"})
            continue
        if candidate.container_side >= current_sides[target] - 1e-10:
            continue
        ok, reason = _certify(target, candidate)
        if ok:
            valid += 1
        else:
            failures.append({"source":n,"target":target,"reason":reason})
        experiment_id = f"l-frame-n{n}-to-{target}"
        updated = False
        if ok:
            if apply:
                try:
                    offer = propose_improvement(
                        registry,
                        {"n":target,"side":candidate.container_side,
                         "squares":[asdict(s) for s in candidate.squares]},
                        source="gerit_l_frame_propagation",
                        experiment_id=experiment_id,
                        generation=0,operator=FAMILY)
                    updated = bool(offer["accepted"])
                except ValueError as error:
                    failures.append({"source":n,"target":target,
                                     "reason":str(error)})
            else:
                updated = True  # Virtual acceptance; no registry write.
            if updated:
                accepted += 1
                current_sides[target] = candidate.container_side
                shadow[target] = {"n":target,"side":candidate.container_side,
                                  "squares":[asdict(s) for s in candidate.squares]}
                lineage[target] = lineage.get(n,[n])+[target]
                transitions.append({"from":n,"to":target,
                                    "chain":lineage[target],
                                    "old_side":initial_sides[target],
                                    "new_side":candidate.container_side})
                print(f"{'UPDATED' if apply else 'WOULD_UPDATE'} "
                      f"N={n} -> N={target} "
                      f"old_L={initial_sides[target]:.12f} "
                      f"new_L={candidate.container_side:.12f} "
                      f"chain={lineage[target]}",flush=True)
        row = {"source_n":n,"target_n":target,
               "source_side":old_side,"previous_target_side":initial_sides[target],
               "candidate_side":candidate.container_side,
               "valid":ok,"validation":reason,
               "accepted":updated,"applied":apply and updated,
               "experiment_id":experiment_id}
        rows.append(row)
        if ledger:
            record_attempt(
                ledger,n=target,family=FAMILY,script=SCRIPT,
                algorithm="deterministic_l_frame_recursive",
                seed=None,
                parameters={"source_n":n,"target_n":target,
                            "source_chain":lineage.get(n,[n]),
                            "strip_length":math.floor(old_side),
                            "dry_run":not apply},
                before_side=initial_sides[target],
                candidate_side=candidate.container_side,valid=ok,
                validation=reason,accepted=apply and updated,
                experiment_id=experiment_id,generation=0,
                note="Validated one-step L-frame generated from archive")
    if apply:
        current_total = read_registry(registry)["total_score"]
    else:
        current_total = math.fsum(
            current_sides[n]/math.sqrt(n)-1 for n in range(1,1001))
        # For max_n < 1000, the untouched remainder stays in bank.
        if max_n < 1000:
            current_total += math.fsum(
                float(bank["problems"][str(n)]["side"])/math.sqrt(n)-1
                for n in range(max_n+1,1001))
    improved_targets = sorted(set(x["to"] for x in transitions))
    result = {
        "family":FAMILY,"applied":apply,"sources_screened":efforts,
        "competitive_offers":eligible,"valid_offers":valid,
        "accepted_transitions":accepted,
        "distinct_improved_targets":len(improved_targets),
        "improved_target_counts":improved_targets,
        "special_30_counts":list(SPECIAL_30),
        "special_30_improved":[n for n in SPECIAL_30 if n in improved_targets],
        "initial_score":float(bank["total_score"]),
        "final_score":current_total,
        "transitions":transitions,"attempts":rows,"failures":failures,
    }
    if report:
        path=Path(report)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite report: {path}")
        path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",
                        encoding="utf-8")
        csv_file=path.with_suffix(".csv")
        with csv_file.open("w",newline="",encoding="utf-8") as f:
            writer=csv.DictWriter(f,fieldnames=[
                "source_n","target_n","source_side","previous_target_side",
                "candidate_side","valid","validation","accepted","applied",
                "experiment_id"])
            writer.writeheader()
            writer.writerows(rows)
    if ledger and summary_csv:
        summarize_ledger(ledger,summary_csv)
    print(f"FINISHED examined={efforts} competitive={eligible} "
          f"valid={valid} transitions={accepted} "
          f"improved_N={len(improved_targets)} "
          f"score={current_total:.12f}",flush=True)
    print(f"IMPROVED TARGET N: {improved_targets}",flush=True)
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--registry",default="results/kaggle_baseline/best_registry.json")
    p.add_argument("--report",default="results/kaggle_l_frame/l_frame_report.json")
    p.add_argument("--ledger",default="results/kaggle_method_ledger.jsonl")
    p.add_argument("--summary",default="results/kaggle_family_reports/method_summary.csv")
    p.add_argument("--max-n",type=int,default=1000)
    p.add_argument("--apply",action="store_true",
                   help="Apply only strictly better interval-validated answers")
    a=p.parse_args()
    propagate(a.registry,apply=a.apply,report=a.report,ledger=a.ledger,
              summary_csv=a.summary,max_n=a.max_n)


if __name__=="__main__":
    main()
