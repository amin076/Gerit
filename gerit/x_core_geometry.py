"""Geometric X-core construction: five edge-connected diamonds + 4 x 3 squares.

A reusable, strictly verified *seed family*, not a stored optimum. The
five center squares are all unit squares rotated by 45 degrees; the four
outer arms exactly share one complete side with the central square in
ideal real arithmetic. Small positive numeric clearance prevents an
accidental SAT penetration from floating-point roundoff.

For N=17, the twelve remaining axis-aligned squares comprise three
positions in one quadrant, repeated under 90-degree rotations. All
seventeen squares are freely movable/rotatable by Gerit's later engine.
"""
from __future__ import annotations

import math
import random

from .geometry import Packing, Square, minimum_bounding_square, validate_packing


def x_core_five_plus_twelve_seed(n: int, rng: random.Random | None = None,
                                 *, clearance: float = 2e-5,
                                 arm_offset: float = .80) -> Packing | None:
    """Generate the exact requested 5+4*3 (N=17) symmetry motif.

    Construction is analytic, not an injected published 17-square record.
    The ideal envelope tends to L=2+2*sqrt(2) as clearance -> 0.
    Return None for other N rather than silently changing the architecture.
    """
    if n != 17:
        return None
    if not (math.isfinite(clearance) and clearance > 0 and
            math.isfinite(arm_offset) and .72 <= arm_offset <= .94):
        raise ValueError("clearance must be positive and arm_offset in [.72,.94]")
    u=1/math.sqrt(2)
    # At clearance zero, each outside diamond is one edge-sharing
    # neighbour of the central diamond, not merely vertex-connected.
    pose=[Square(0.,0.,math.pi/4)]
    for sx in (-1,1):
        for sy in (-1,1):
            pose.append(Square(sx*(u+clearance),sy*(u+clearance),math.pi/4))
    # The axis-oriented 3-square L-shaped group can fit in each diagonal
    # quadrant. Offset is geometric: r = sqrt(2)+1/2 (plus clearance).
    r=math.sqrt(2)+.5+3*clearance
    group=((r,arm_offset),(arm_offset,r),(r,r))
    for quarter in range(4):
        theta=quarter*math.pi/2
        c,s=math.cos(theta),math.sin(theta)
        for x,y in group:
            pose.append(Square(x*c-y*s,x*s+y*c,0.))
    # minimum_bounding_square rebases coordinates to zero. At zero SAT
    # tolerance, floating-point subtraction can place a boundary vertex
    # at -2e-16 even for exact analytic inside geometry. A microscopic
    # padding protects strict containment without hiding any collision.
    raw=minimum_bounding_square(pose)
    pad=1e-9
    packing=Packing(tuple(Square(s.x+pad,s.y+pad,s.angle) for s in raw.squares),
                    raw.container_side+2*pad)
    if len(packing.squares)!=17 or not validate_packing(packing,tolerance=0.).valid:
        raise ValueError("X-core arrangement unexpectedly violates strict SAT")
    return packing
