"""Headless population-image and research-chart generation for Gerit."""
from __future__ import annotations
import math
from pathlib import Path
from PIL import Image, ImageDraw
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .geometry import Packing, square_vertices

COLORS = ('#6699cc','#6fba96','#eeb76b','#b494d5','#db8593',
          '#b5bf77','#77b9c2','#bbafa0','#d9aa70','#a1a0df',
          '#7cc4a1','#c88e7e')


def draw_population(path: Path, members: list[tuple[int, Packing]],
                    side_cap: float | None = 5.0, columns: int = 5) -> None:
    """Draw selected packings; None means each tile uses its actual side L."""
    tile, plot, margin = 124, 95, 12
    cols = min(columns, len(members))
    image = Image.new('RGB', (cols * tile, math.ceil(len(members) / cols) * tile), 'white')
    draw = ImageDraw.Draw(image)
    for index, (_, packing) in enumerate(members):
        ox = (index % cols) * tile + margin
        oy = (index // cols) * tile + margin
        draw.rectangle((ox,oy,ox+plot,oy+plot), outline='#344455', width=2)
        tile_side = packing.container_side if side_cap is None else side_cap
        for j, square in enumerate(packing.squares):
            pts = [(round(ox + x / tile_side * plot),
                    round(oy + (tile_side - y) / tile_side * plot))
                   for x,y in square_vertices(square)]
            draw.polygon(pts, fill=COLORS[j % len(COLORS)])
            draw.line(pts+[pts[0]], fill='#293a47', width=1)
        draw.text((ox, oy+plot+2),f'L={packing.container_side:.5f}',fill='#222222')
    image.save(path)


def draw_best(path: Path, packing: Packing) -> None:
    fig, ax = plt.subplots(figsize=(6,6))
    for j, square in enumerate(packing.squares):
        pts = list(square_vertices(square))
        xs = [x for x,_ in pts+[pts[0]]]
        ys = [y for _,y in pts+[pts[0]]]
        ax.fill(xs,ys,color=COLORS[j%len(COLORS)], alpha=.55)
        ax.plot(xs,ys,color='#303747',linewidth=1.0)
        ax.text(square.x,square.y,str(j+1),ha='center',va='center',fontsize=8)
    side=packing.container_side
    ax.plot([0,side,side,0,0],[0,0,side,side,0],color='black',lw=1)
    ax.set(xlim=(-.05,side+.05),ylim=(-.05,side+.05),
           title=f'Gerit: {len(packing.squares)} unit squares — best L={side:.10f}')
    ax.set_aspect('equal')
    fig.tight_layout()
    fig.savefig(path,dpi=150)
    plt.close(fig)


def draw_progress(path: Path, generations: list[dict], grid_reference_side: float=4.0) -> None:
    fig, ax = plt.subplots(figsize=(9,4.8))
    ax.plot([r['generation'] for r in generations],
            [r['best_side'] for r in generations], lw=1.8)
    ax.axhline(grid_reference_side,ls='--',lw=1,color='gray',
               label=f'Known grid baseline L={grid_reference_side:g}')
    ax.set(xlabel='Generation',ylabel='Best enclosing side L',
           title='Gerit evolutionary search — inherited policy continuation')
    ax.grid(alpha=.18)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path,dpi=150)
    plt.close(fig)