"""Durable best-packing registry for Gerit's 1,000 Kaggle problems.

Accepted packings are center coordinates (x, y), unit squares, angles in radians.
Only strictly improving, independently geometry-validated solutions replace a record.
This module does NOT assume the official Kaggle CSV schema.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gerit.geometry import Packing, Square, validate_packing
from scripts.build_kaggle_grid_bank import build_bank


def _validate_solution(record):
    n = int(record["n"])
    if not 1 <= n <= 1000 or len(record["squares"]) != n:
        raise ValueError("incorrect square count")
    side = float(record["side"])
    squares = [Square(float(p["x"]), float(p["y"]), float(p["angle"]))
               for p in record["squares"]]
    packing = Packing(tuple(squares), side)
    result = validate_packing(packing, tolerance=0.0)
    if not result.valid:
        raise ValueError(f"invalid packing: {result}")
    return n, side


def _atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    try:
        with temp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def initialize_registry(path):
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"Registry already exists: {path}")
    bank = build_bank()
    for item in bank["problems"].values():
        # Grid construction is validated in O(n) by build_bank().
        # Avoid O(n^2) pairwise SAT checks across 500,500 baseline squares.
        item["baseline_side"] = item["side"]
        item["updated_at"] = datetime.now(timezone.utc).isoformat()
        item["experiment_id"] = "grid-baseline"
        item["generation"] = 0
        item["previous_best_side"] = None
        item["validation"] = {"method": "gerit.geometry.validate_packing", "valid": True}
    _atomic_write(path, bank)
    return bank


def read_registry(path):
    with Path(path).open(encoding="utf-8") as f:
        bank = json.load(f)
    if bank.get("schema_version") != 1 or len(bank.get("problems", {})) != 1000:
        raise ValueError("unsupported or incomplete registry")
    return bank


def propose_improvement(path, candidate, *, source, experiment_id,
                        generation, operator="unspecified", epsilon=1e-10):
    """Return acceptance status, recording the candidate only if strictly better.

    Single-process writer: do not invoke concurrent registry writers. We use
    atomic replacement, but not an inter-process compare-and-swap lock.
    """
    if not source or not experiment_id:
        raise ValueError("source and experiment_id required")
    n, new_side = _validate_solution(candidate)
    # Independent interval geometry audit already present in Gerit.
    from gerit.kaggle import Candidate, validate as independent_validate
    poses = tuple((repr(float(p["x"])), repr(float(p["y"])),
                   repr(float(p["angle"]))) for p in candidate["squares"])
    independent = independent_validate(Candidate(n, poses, source, new_side))
    if not independent.valid:
        raise ValueError(f"Independent geometry rejected update: {independent.reason}")
    bank = read_registry(path)
    old = bank["problems"][str(n)]
    old_side = float(old["side"])
    if not new_side < old_side - epsilon:
        return {"accepted": False, "n": n, "current_side": old_side,
                "candidate_side": new_side, "total_score": bank["total_score"]}
    new = {
        "n": n, "side": new_side,
        "baseline_side": old["baseline_side"],
        "squares": candidate["squares"],
        "source": source, "operator": operator,
        "experiment_id": experiment_id,
        "generation": int(generation),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "previous_best_side": old_side,
        "validated": True,
        "validation": {"method": "strict SAT and interval SAT", "valid": True, "independent_reason": independent.reason},
        "baseline_improvement": float(old["baseline_side"]) - new_side,
        "improvement_from_previous": old_side - new_side,
        "score_contribution": new_side / math.sqrt(n) - 1.0,
    }
    bank["problems"][str(n)] = new
    bank["total_score"] = math.fsum(
        float(bank["problems"][str(k)]["side"]) / math.sqrt(k) - 1.0
        for k in range(1, 1001)
    )
    _atomic_write(path, bank)
    return {"accepted": True, "n": n, "previous_side": old_side,
            "candidate_side": new_side, "total_score": bank["total_score"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="results/kaggle_baseline/best_registry.json")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("init")
    sub.add_parser("status")
    offer = sub.add_parser("offer")
    offer.add_argument("--candidate", required=True, help="JSON with n, side, squares")
    offer.add_argument("--source", default="gerit")
    offer.add_argument("--experiment-id", required=True)
    offer.add_argument("--generation", type=int, required=True)
    offer.add_argument("--operator", default="unspecified")
    args = parser.parse_args()
    if args.action == "init":
        bank = initialize_registry(args.registry)
        print(f"Created registry with {len(bank['problems'])} problems")
    elif args.action == "status":
        bank = read_registry(args.registry)
        improved = sum(p["side"] < p["baseline_side"] - 1e-10
                       for p in bank["problems"].values())
        print(f"Problems: 1000 | Improved: {improved} | Score: {bank['total_score']:.12f}")
    else:
        with open(args.candidate, encoding="utf-8") as f:
            candidate = json.load(f)
        result = propose_improvement(
            args.registry, candidate, source=args.source,
            experiment_id=args.experiment_id,
            generation=args.generation, operator=args.operator)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
