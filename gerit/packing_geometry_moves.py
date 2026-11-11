"""Unrestricted packing geometry moves; separate from Gerit's evolutionary engine.

A pivot-square can rotate while neighbors move together toward/away from it.
The pivot is selected by geometry (usually centrality), not square index.
All squares remain eligible for rotation, translation and structural changes.
No known packing, target side length or five-square optimal angle is embedded.
"""
from __future__ import annotations
import math
import random

from .geometry import Packing, Square, minimum_bounding_square, validate_packing


def propose_pivot_release(parent: Packing, rng: random.Random, side_cap: float,
                          *, attempts: int = 96) -> Packing | None:
    """Simultaneously release, rotate and translate multiple unit squares.

    Samples radial contraction/expansion, an independently rotated pivot,
    and sometimes independent rotations of all other squares. Strict SAT
    collision checks occur after full coordinated moves. Works for any N>=2.
    """
    squares=parent.squares
    if len(squares)<2 or not math.isfinite(side_cap) or side_cap<1.0:
        return None
    cx=sum(s.x for s in squares)/len(squares)
    cy=sum(s.y for s in squares)/len(squares)
    central=sorted(range(len(squares)),
                   key=lambda i:(squares[i].x-cx)**2+(squares[i].y-cy)**2)
    for _ in range(attempts):
        pivot_index=(central[0] if rng.random()<.7 else rng.randrange(len(squares)))
        pivot=squares[pivot_index]
        # Let the surrounding geometry open up *or* contract.
        radial_factor=rng.uniform(.76,1.16)
        # The pivot is not assigned a fixed optimal orientation.
        pivot_rotation=(rng.uniform(-.85,.85) if rng.random()<.65
                        else rng.gauss(0.,.20))
        pivot_shift_x=rng.gauss(0,.025)
        pivot_shift_y=rng.gauss(0,.025)
        changed=[]
        for i,s in enumerate(squares):
            if i==pivot_index:
                changed.append(Square(s.x+pivot_shift_x,s.y+pivot_shift_y,
                                      s.angle+pivot_rotation))
            else:
                # All squares can rotate, but leave a high probability of
                # small rotations to avoid losing viable dense contact.
                rotation=rng.gauss(0,.05) if rng.random()<.30 else 0.
                changed.append(Square(
                    pivot.x+(s.x-pivot.x)*radial_factor+rng.gauss(0,.012),
                    pivot.y+(s.y-pivot.y)*radial_factor+rng.gauss(0,.012),
                    s.angle+rotation))
        child=minimum_bounding_square(changed)
        if child.container_side<=side_cap+1e-10 and validate_packing(child,tolerance=0).valid:
            return child
    return None
