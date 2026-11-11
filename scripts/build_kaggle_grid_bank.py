"""Build and validate a complete 1..1000 grid-packing baseline.

This is an internal solution bank, NOT an official Kaggle submission.
Coordinates are square centers; angles are radians.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path


def grid_solution(n: int) -> dict:
    if not 1 <= n <= 1000:
        raise ValueError("n must be between 1 and 1000")
    side = math.isqrt(n)
    if side * side < n:
        side += 1
    squares = [
        {"x": float(i % side) + 0.5,
         "y": float(i // side) + 0.5,
         "angle": 0.0}
        for i in range(n)
    ]
    return {"n": n, "side": float(side), "squares": squares,
            "source": "analytic_grid", "validated": False}


def validate_grid(record: dict) -> None:
    n = record["n"]
    side = record["side"]
    squares = record["squares"]
    expected = math.isqrt(n) + (math.isqrt(n) ** 2 < n)
    if side != expected or len(squares) != n:
        raise ValueError(f"invalid side/count for n={n}")
    seen = set()
    for square in squares:
        x, y, angle = square["x"], square["y"], square["angle"]
        if not all(math.isfinite(v) for v in (x, y, angle)):
            raise ValueError(f"nonfinite square at n={n}")
        if angle != 0 or x % 1 != 0.5 or y % 1 != 0.5:
            raise ValueError(f"off-grid square at n={n}")
        if not (0.5 <= x <= side - 0.5 and 0.5 <= y <= side - 0.5):
            raise ValueError(f"out-of-bounds square at n={n}")
        if (x, y) in seen:
            raise ValueError(f"overlap at n={n}")
        seen.add((x, y))
    record["validated"] = True


def build_bank() -> dict:
    problems = {}
    contributions = []
    for n in range(1, 1001):
        record = grid_solution(n)
        validate_grid(record)
        score = record["side"] / math.sqrt(n) - 1
        record["score_contribution"] = score
        problems[str(n)] = record
        contributions.append(score)
    return {
        "schema_version": 1,
        "coordinate_convention": "unit-square centers, radians",
        "score_status": "provisional; verify against official competition rules",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_score": math.fsum(contributions),
        "total_square_records": sum(range(1, 1001)),
        "problems": problems,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="results/kaggle_baseline/grid_bank.json")
    args = parser.parse_args()
    bank = build_bank()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_name(output.name + ".tmp")
    try:
        with temp.open("w", encoding="utf-8") as file:
            json.dump(bank, file, separators=(",", ":"), allow_nan=False)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp, output)
    finally:
        temp.unlink(missing_ok=True)
    print(f"Validated problems: {len(bank['problems'])}")
    print(f"Square records: {bank['total_square_records']}")
    print(f"Provisional baseline score: {bank['total_score']:.12f}")
    print(f"Saved: {output}")


if __name__ == "__main__":
    main()
