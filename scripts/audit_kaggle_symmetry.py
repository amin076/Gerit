"""Evaluate ALL existing Gerit symmetry families before evolutionary search.

This is a deterministic, independent geometry audit. It does not select or
restrict genetic parents and does not start evolution. A strictly better
candidate can update the 1000-answer archive after interval SAT validation.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gerit.geometry import Packing, validate_packing
from gerit.symmetry_operators import OPERATORS, geometry_seed_bank
from scripts.kaggle_best_registry import read_registry, propose_improvement


def symmetry_candidates(n: int, seed: int, copies: int = 3) -> list[tuple[str, Packing]]:
    """Every existing geometry family, not only the six chosen founder slots.

    horizontal/vertical, diagonal pairs, fourfold rotation, corner clusters,
    and other existing Gerit families are all evaluated. For 4*m*m+1 counts,
    particularly N=5 and N=17, the center-45-degree family is included.
    """
    if type(n) is not int or not 1 <= n <= 1000:
        raise ValueError("n must be 1..1000")
    if type(copies) is not int or copies < 1:
        raise ValueError("copies must be positive")
    output = geometry_seed_bank(n, seed, copies=copies)
    if n == 5:
        from experiments.five_squares.optimizer import best_inward_for_angle
        packing, _ = best_inward_for_angle(math.pi / 4)
        output.append(("four_corners_center_45", packing))
    # 4*m*m+1 (m>=2) is covered by OPERATORS.four_corner_clusters.
    return [(name, packing) for name, packing in output
            if packing is not None and len(packing.squares) == n
            and validate_packing(packing, tolerance=0.0).valid]


def evaluate_one(n: int, seed: int, copies: int, registry: str, *,
                 apply: bool = False, output_dir: Path | None = None) -> dict:
    initial = read_registry(registry)["problems"][str(n)]
    candidates = symmetry_candidates(n, seed, copies)
    families: dict[str, dict] = {}
    for name, packing in candidates:
        data = families.setdefault(name, {
            "tested": 0, "best_side": None, "best": None})
        data["tested"] += 1
        if data["best_side"] is None or packing.container_side < data["best_side"]:
            data["best_side"] = packing.container_side
            data["best"] = packing
    ordered = sorted(families.items(), key=lambda item: item[1]["best_side"])
    # We try better records in increasing side order. An uncertifiable
    # candidate is reported rather than blocking another valid candidate.
    accepted = []
    rejected = []
    if apply:
        for name, data in ordered:
            if data["best_side"] >= float(read_registry(registry)["problems"][str(n)]["side"]) - 1e-10:
                continue
            packing = data["best"]
            record = {
                "n": n, "side": packing.container_side,
                "squares": [asdict(sq) for sq in packing.squares],
            }
            try:
                change = propose_improvement(
                    registry, record, source="gerit_symmetry_preflight",
                    experiment_id=f"symmetry-n{n}-seed{seed}",
                    generation=0, operator=name)
                if change["accepted"]:
                    accepted.append({"family": name, "side": packing.container_side})
                    break
            except ValueError as exc:
                rejected.append({"family": name, "error": str(exc)})
    rows = [{"family": name, "tested": data["tested"],
             "best_side": data["best_side"],
             "beats_original_registry": data["best_side"] < float(initial["side"]) - 1e-10}
            for name, data in ordered]
    summary = {
        "n": n, "seed": seed, "copies": copies,
        "initial_registry_side": float(initial["side"]),
        "final_registry_side": float(read_registry(registry)["problems"][str(n)]["side"]),
        "candidate_count": len(candidates),
        "family_count": len(families),
        "families": rows, "accepted": accepted,
        "uncertifiable": rejected,
        "updated": bool(accepted), "apply": apply,
    }
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / f"n{n}-symmetry-seed{seed}.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"SYMMETRY N={n} tested={len(candidates)} "
          f"families={len(families)} stored={initial['side']:.12f} "
          f"best={rows[0]['best_side']:.12f} "
          f"accepted={bool(accepted)}", flush=True)
    for row in rows:
        print(f"  {row['family']:<26} L={row['best_side']:.12f} "
              f"tested={row['tested']} beats_original={row['beats_original_registry']}",
              flush=True)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--counts", nargs="+", type=int, default=[17, 18, 19, 20])
    parser.add_argument("--seed", type=int, default=2715)
    parser.add_argument("--copies", type=int, default=3)
    parser.add_argument("--registry", default="results/kaggle_baseline/best_registry.json")
    parser.add_argument("--output-dir", type=Path, default=Path("results/kaggle_symmetry_audit"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    if len(set(args.counts)) != len(args.counts) or args.copies < 1:
        parser.error("Unique counts and positive copies required")
    for n in args.counts:
        evaluate_one(n, args.seed+n, args.copies, args.registry,
                     apply=args.apply, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
