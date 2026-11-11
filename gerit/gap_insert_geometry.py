"""Find one more unit square inside an already-good enclosing square.

This method is NOT a pure-grid mutation. Every existing accepted packing
is treated as fixed, and we look for an additional free square using a
geometrically screened set of center positions and rotation angles. The
candidate may be inside a void or straddle the packing's current bounds,
provided its NEW tight enclosing square improves the current N+1 record.
"""
from __future__ import annotations

import math
import random

from .geometry import Packing, Square, minimum_bounding_square, squares_overlap


def valid_one_more(source: Packing, max_side: float, *,
                   seed=0, samples=1000,
                   angles=(0., math.pi/12,math.pi/6,math.pi/4)):
    if not math.isfinite(max_side) or max_side <= 0 or samples<1:
        raise ValueError("Invalid search bounds")
    base=minimum_bounding_square(source.squares)
    if base.container_side >= max_side-1e-8:
        return None,0
    rng=random.Random(seed)
    existing=base.squares
    margin=2e-5
    # Anchor sites on lattice pockets and near other square boundaries.
    # This is a screening heuristic: exhaustive only at chosen sites,
    # and does NOT prove nonexistence when no placement is found.
    sites=[]
    # Full quarter grid for small squares, fractional positions for larger.
    step=.25 if max_side<=8 else (.5 if max_side<=16 else 1.)
    i=0
    while (i+.5)*step < max_side:
        j=0
        x=(i+.5)*step
        while (j+.5)*step < max_side:
            sites.append((x,(j+.5)*step))
            j+=1
        i+=1
    # Corners of existing squares plus offset placements.
    choices=list(existing)
    if len(choices)>80:
        choices=rng.sample(choices,80)
    for s in choices:
        for dx,dy in ((1+margin,0),(-1-margin,0),(0,1+margin),(0,-1-margin),
                      (.75,.75),(-.75,.75),(.75,-.75),(-.75,-.75)):
            sites.append((s.x+dx,s.y+dy))
    # Random pocket probes, reproducible by seed.
    sites += [(rng.uniform(.5,max_side-.5),rng.uniform(.5,max_side-.5))
              for _ in range(samples)]
    rng.shuffle(sites)
    trials=0
    best=None
    best_side=max_side
    # Broad phase: squares farther than 1.42 in BOTH axes cannot overlap.
    # Check only promising nearby poses; full independent verification occurs
    # before writing to the answer registry.
    for x,y in sites:
        for angle in angles:
            radius=(abs(math.cos(angle))+abs(math.sin(angle)))/2
            if not(radius+margin<=x<=max_side-radius-margin
                   and radius+margin<=y<=max_side-radius-margin):
                continue
            new=Square(x,y,angle)
            trials+=1
            if any(abs(x-old.x)<1.42 and abs(y-old.y)<1.42
                   and squares_overlap(new,old,tolerance=0.)
                   for old in existing):
                continue
            candidate=minimum_bounding_square((*existing,new))
            if candidate.container_side >= best_side-1e-9:
                continue
            best,best_side=candidate,candidate.container_side
    return best,trials
