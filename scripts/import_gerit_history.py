"""Discover and optionally import actual historical Gerit packings.

Only files containing full coordinates are eligible. Imported records are
validated by the strict geometry validator and accepted only if improving.
Default mode is dry-run; --apply explicitly updates the registry.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.kaggle_best_registry import read_registry, propose_improvement, _validate_solution

FILENAMES = {
    "best_result.json", "best.json", "selected_population_final.json",
    "run_result.json", "final_result.json",
}
MAX_BYTES = 20_000_000


def candidates_from_document(data):
    """Extract only complete coordinate-bearing entries, never reconstruct from side."""
    if not isinstance(data, dict):
        return
    if isinstance(data.get("best"), dict):
        yield data["best"], "best"
    if isinstance(data.get("best_packing"), dict):
        yield data["best_packing"], "best_packing"
    for key in ("selected_members", "population", "members"):
        members = data.get(key)
        if isinstance(members, list):
            for i, member in enumerate(members):
                if isinstance(member, dict):
                    yield member, f"{key}[{i}]"
    if isinstance(data.get("squares"), list):
        yield data, "root"


def normalize(raw):
    """Recognize schemas observed in the Gerit repository; reject guesses."""
    squares = raw.get("squares")
    if not isinstance(squares, list) or not squares:
        raise ValueError("missing complete squares list")
    side = raw.get("container_side", raw.get("side"))
    if side is None:
        raise ValueError("missing side")
    values = []
    for square in squares:
        if not isinstance(square, dict) or not {"x", "y"}.issubset(square):
            raise ValueError("missing square coordinates")
        values.append({"x": float(square["x"]), "y": float(square["y"]),
                       "angle": float(square.get("angle", 0.0))})
    return {"n": len(values), "side": float(side), "squares": values}


def discover(folder, n):
    folder = Path(folder)
    if not folder.is_dir():
        raise NotADirectoryError(folder)
    for path in sorted(folder.rglob("*.json")):
        if path.name not in FILENAMES:
            continue
        if path.stat().st_size > MAX_BYTES:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for raw, label in candidates_from_document(data):
                try:
                    candidate = normalize(raw)
                    if candidate["n"] != n:
                        continue
                    _validate_solution(candidate)
                    yield path, label, candidate
                except (ValueError, KeyError, TypeError, OverflowError):
                    continue
        except (OSError, ValueError, UnicodeError):
            continue


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="results")
    parser.add_argument("--n", type=int, default=5)
    parser.add_argument("--registry", default="results/kaggle_baseline/best_registry.json")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.n <= 1000:
        parser.error("n must be from 1 to 1000")
    current = read_registry(args.registry)["problems"][str(args.n)]["side"]
    found = list(discover(args.root, args.n))
    print(f"VALID_PACKINGS={len(found)} N={args.n} STORED_BEST={current:.12f}", flush=True)
    unique = {}
    for path, label, candidate in found:
        key = (str(path), label)
        unique[key] = candidate
    ranked = sorted(((p, label, c) for (p, label), c in unique.items()),
                    key=lambda item: item[2]["side"])
    for path, label, candidate in ranked[:15]:
        print(f"L={candidate['side']:.12f} SOURCE={path} ENTRY={label}", flush=True)
    if not ranked:
        print("NO_VALID_COORDINATE_RECORDS_FOUND")
        return
    path, label, best = ranked[0]
    if not args.apply:
        print("DRY_RUN: no changes. Add --apply to import the best valid packing.")
        return
    response = propose_improvement(
        args.registry, best, source=f"gerit_historical:{path}:{label}",
        experiment_id=f"historical-import-n{args.n}",
        generation=0, operator="historical_import")
    print("IMPORT_RESULT=" + json.dumps(response, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
