"""Visualize a single 45-degree square sliding through a FROZEN N=901 packing.

The 900 axis-aligned unit squares and the container side do not move.
The moving diamond follows center -> top-edge midpoint -> top-right corner.
Each frame is explicitly labelled valid/overlapping. The later frames are
*not* packings: relocating the other squares is a separate future experiment.

Outputs: frame_*.png, contact_sheet.png, manifest.json (and optional GIF).
Usage:
  py -3 scripts/plot_901_diamond_path.py --frames-up 9 --frames-corner 9
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gerit.four_corner_center_45 import four_corner_center_45
from gerit.geometry import Square, square_vertices, squares_overlap, square_inside_container


def interpolate(a: tuple[float, float], b: tuple[float, float], t: float):
    return (a[0] * (1 - t) + b[0] * t, a[1] * (1 - t) + b[1] * t)


def make_path(side: float, up: int, across: int):
    if up < 2 or across < 2:
        raise ValueError("Each segment requires at least 2 frames")
    h = math.sqrt(0.5)  # half projected width of 45-degree unit square
    center = (side / 2, side / 2)
    top = (side / 2, side - h)
    corner = (side - h, side - h)
    frames = []
    for i in range(up):
        frames.append(("center_to_top", interpolate(center, top, i / (up - 1))))
    for i in range(1, across):
        frames.append(("top_to_corner", interpolate(top, corner, i / (across - 1))))
    return frames


def inspect(moving: Square, stationary: tuple[Square, ...], side: float):
    # Broad-phase is conservative: any unit-square overlap has center
    # separation less than 1.5 units in x and y for this angle combination.
    hits = []
    for i, s in enumerate(stationary):
        if abs(s.x - moving.x) > 1.5 or abs(s.y - moving.y) > 1.5:
            continue
        if squares_overlap(s, moving, tolerance=1e-10):
            hits.append(i)
    inside = square_inside_container(moving, side, tolerance=1e-9)
    return hits, inside


def plot_frame(path: Path, stationary: tuple[Square, ...], diamond: Square,
               side: float, frame_num: int, stage: str, hits: list[int],
               inside: bool, dpi: int):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import PatchCollection
    from matplotlib.patches import Polygon, Rectangle

    fig, ax = plt.subplots(figsize=(8, 8), layout="constrained")
    patches = [Rectangle((s.x - 0.5, s.y - 0.5), 1, 1) for s in stationary]
    ax.add_collection(PatchCollection(
        patches, facecolor="#c6e2ff", edgecolor="#4778a7", linewidth=0.22))
    for i in hits:
        s = stationary[i]
        ax.add_patch(Rectangle((s.x - .5, s.y - .5), 1, 1,
                               facecolor="#fca5a5", edgecolor="#b91c1c",
                               linewidth=1.2, zorder=3))
    ax.add_patch(Polygon(square_vertices(diamond), closed=True,
                         facecolor="#fb923c", edgecolor="#9a3412",
                         linewidth=1.9, zorder=5))
    ax.add_patch(Rectangle((0, 0), side, side, fill=False,
                           edgecolor="#111827", linewidth=1.6, zorder=6))
    ax.plot(diamond.x, diamond.y, "o", markersize=2.5, color="#7c2d12", zorder=7)
    status = "VALID" if inside and not hits else f"ILLUSTRATION ONLY: {len(hits)} overlaps"
    ax.set_title(f"N=901  |  frame {frame_num:02d}  |  {stage}\n"
                 f"L fixed = {side:.12f}  |  {status}", fontsize=11)
    ax.set_xlim(-.3, side + .3)
    ax.set_ylim(-.3, side + .3)
    ax.set_aspect("equal")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    fig.savefig(path, dpi=dpi)
    plt.close(fig)


def contact_sheet(paths: list[Path], outfile: Path, cols: int):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = math.ceil(len(paths) / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(3.6 * cols, 3.8 * rows))
    axs = list(axes.flat) if hasattr(axes, "flat") else [axes]
    for ax, path in zip(axs, paths):
        ax.imshow(plt.imread(path))
        ax.set_title(path.stem, fontsize=9)
        ax.axis("off")
    for ax in axs[len(paths):]:
        ax.axis("off")
    fig.tight_layout()
    fig.savefig(outfile, dpi=110)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--frames-up", type=int, default=9)
    p.add_argument("--frames-corner", type=int, default=9)
    p.add_argument("--output-dir", type=Path, default=Path("results/diamond_path_901"))
    p.add_argument("--dpi", type=int, default=140)
    p.add_argument("--sheet-columns", type=int, default=4)
    a = p.parse_args()
    if a.sheet_columns < 1 or a.dpi < 30:
        p.error("sheet-columns >= 1 and dpi >= 30 are required")
    if a.output_dir.exists() and any(a.output_dir.iterdir()):
        p.error("Output directory is not empty; choose a new one to preserve results")

    founder = four_corner_center_45(901, spacing=1e-7, safety=1e-6)
    side = founder.container_side  # constant for ALL frames
    stationary = founder.squares[:-1]
    assert len(stationary) == 900
    assert len(founder.squares) == 901
    path = make_path(side, a.frames_up, a.frames_corner)

    frames_dir = a.output_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "n": 901, "stationary_unit_squares": 900,
        "fixed_side": side, "ideal_limit": 30 + math.sqrt(0.5),
        "description": "Freeze all 900 squares and move only the 45-degree diamond.",
        "warning": "Overlapping frames are illustrations, not valid packings.",
        "frames": [],
    }
    filenames = []
    for i, (stage, (x, y)) in enumerate(path):
        square = Square(x, y, math.pi / 4)
        hits, inside = inspect(square, stationary, side)
        filename = frames_dir / f"frame_{i:02d}.png"
        plot_frame(filename, stationary, square, side, i, stage,
                   hits, inside, a.dpi)
        filenames.append(filename)
        item = {
            "index": i, "stage": stage,
            "x": x, "y": y, "angle_degrees": 45,
            "side": side, "outside_container": not inside,
            "overlap_count": len(hits), "overlap_stationary_indices": hits,
            "valid_with_unchanged_900": inside and not hits,
            "image": str(filename),
        }
        manifest["frames"].append(item)
        print(f"FRAME {i:02d}/{len(path)-1:02d} {stage} "
              f"center=({x:.6f},{y:.6f}) overlaps={len(hits)} "
              f"inside={inside} fixed_L={side:.12f}", flush=True)

    contact_sheet(filenames, a.output_dir / "contact_sheet.png", a.sheet_columns)
    (a.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("FINISHED frames=", len(path), "output=", a.output_dir, flush=True)


if __name__ == "__main__":
    main()
