"""Draw two REAL, certified square packings: N=5 and N=17.

Uses the existing Gerit geometric founder and the existing draw_best plotter.
All squares are rigid 1x1. One central square is rotated by 45 degrees.
No display scaling, no artificial packing, no evolutionary search.
Run from the Gerit repository root:
    py -3 scripts/plot_center45_5_17.py
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

from gerit.four_corner_center_45 import four_corner_center_45
from gerit.geometry import validate_packing
from gerit.kaggle import Candidate, validate as validate_interval
from gerit.visualization import draw_best


def run(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    for n in (5, 17):
        # This is the exact existing Gerit construction, not a new drawing model.
        packing = four_corner_center_45(n)
        strict = validate_packing(packing, tolerance=0.0)
        if not strict.valid:
            raise RuntimeError(
                f"N={n}: overlaps={strict.overlap_pairs} "
                f"outside={strict.outside_indices}"
            )

        candidate = Candidate(
            n,
            tuple((repr(s.x), repr(s.y), repr(s.angle))
                  for s in packing.squares),
            "gerit_center45_exact",
            packing.container_side,
        )
        certified = validate_interval(candidate)
        if not certified.valid:
            raise RuntimeError(f"N={n}: interval SAT failed: {certified.reason}")

        assert len(packing.squares) == n
        assert sum(abs(s.angle - math.pi / 4) < 1e-12
                   for s in packing.squares) == 1

        image = output_dir / f"center45_n{n}.png"
        data = output_dir / f"center45_n{n}.json"

        # Use exactly the earlier Gerit rendering implementation.
        draw_best(image, packing)
        data.write_text(
            json.dumps({
                "n": n,
                "side": packing.container_side,
                "certification": certified.reason,
                "squares": [asdict(s) for s in packing.squares],
            }, indent=2) + "\n",
            encoding="utf-8",
        )
        print(
            f"VALID N={n} L={packing.container_side:.12f} "
            f"rotated=1 interval={certified.reason} image={image}",
            flush=True,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path,
        default=Path("results/center45_5_17"),
    )
    args = parser.parse_args()
    run(args.output_dir)


if __name__ == "__main__":
    main()
