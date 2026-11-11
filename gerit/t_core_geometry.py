"""Three-armed T diamond core for 17 unit-square packing experiments.

Starting from the X-core family: remove exactly ONE diagonal diamond arm,
retain the 12 three-square quadrant groups, and place the 17th axis-aligned
square inside the freed quadrant. Thus the central motif is four *rotated*
squares: 1 central and 3 full-edge-adjacent arms, not an X.

Independent geometry-only founder: no fitness, parent selection, archive
or published optimal packing is used.
"""
from __future__ import annotations

import math
import random

from .geometry import Packing, Square, minimum_bounding_square, validate_packing

QUADRANTS = ("ne", "nw", "sw", "se")
SIGNS = {"ne": (1, 1), "nw": (-1, 1), "sw": (-1, -1), "se": (1, -1)}


def t_core_three_arm_seed(
    n: int,
    rng: random.Random | None = None,
    *,
    missing_quadrant: str = "se",
    clearance: float = 2e-5,
    arm_offset: float = .80,
) -> Packing | None:
    """Create a 3-arm T rotated 45 degrees, plus 13 axis-aligned squares.

    1 central diamond + 3 full-edge-neighbour diamonds + 12 exterior squares
    (3 in each quadrant) + 1 inserted axis square in the missing-arm void.
    The X-core exterior is retained for controlled comparison. The envelope
    approaches 2 + 2*sqrt(2); a tiny positive clearance avoids roundoff
    penetration. Return None for N != 17.

    missing_quadrant controls which of the four diamond arms is removed.
    Orientation variants are rigid rotations, and can be separately tested.
    """
    if n != 17:
        return None
    if missing_quadrant not in SIGNS:
        raise ValueError("Unknown missing_quadrant: " + str(missing_quadrant))
    if (not math.isfinite(clearance) or clearance <= 0 or
            not math.isfinite(arm_offset) or
            not .72 <= arm_offset <= .94):
        raise ValueError("Invalid clearance/arm_offset")
    u=1/math.sqrt(2)
    squares=[Square(0.,0.,math.pi/4)]
    for quad in QUADRANTS:
        if quad != missing_quadrant:
            sx,sy=SIGNS[quad]
            squares.append(Square(sx*(u+clearance),
                                  sy*(u+clearance), math.pi/4))

    # Same four sets of 3 exterior squares as X, rotated around the center.
    r=math.sqrt(2)+.5+3*clearance
    group=((r,arm_offset),(arm_offset,r),(r,r))
    for q in range(4):
        a=q*math.pi/2
        c,s=math.cos(a),math.sin(a)
        for x,y in group:
            squares.append(Square(x*c-y*s,x*s+y*c,0.))

    # Occupy the void freed by the missing diamond. Choosing arm_offset+.06
    # leaves a nonzero gap from both neighbouring axis-aligned rows and
    # the central rotated diamond, without extending the outer envelope.
    sx,sy=SIGNS[missing_quadrant]
    inset=arm_offset+.06
    squares.append(Square(sx*inset,sy*inset,0.))

    if len(squares)!=17:
        raise RuntimeError("T-core construction must have 17 squares")
    raw=minimum_bounding_square(squares)
    padding=1e-9
    result=Packing(
        tuple(Square(s.x+padding,s.y+padding,s.angle) for s in raw.squares),
        raw.container_side+2*padding,
    )
    checked=validate_packing(result,tolerance=0.)
    if not checked.valid:
        raise ValueError(
            "T-core invalid: overlaps=" + str(checked.overlap_pairs) +
            " outside=" + str(checked.outside_indices))
    return result
