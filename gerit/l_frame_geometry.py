"""Propagate square packings with an axis-aligned L-frame.

Given a valid N-square packing of measured side L, let k=floor(L).
Append k squares above, k squares to the right, and one in the new
outer corner. The resulting packing has N+2*k+1 unit squares and is
contained within a square of side L+1.

An ascending sweep of N=1..1000 makes improvements from earlier targets
available as sources for subsequent targets in the same pass. The
candidate geometry is ALWAYS checked; the formula is not proof that a
particular input packing is valid.
"""
from __future__ import annotations

import math

from .geometry import Packing, Square, minimum_bounding_square


def l_frame_target(source_n: int, source_side: float, *, limit: int = 1000) -> int | None:
    if type(source_n) is not int or source_n < 1:
        raise ValueError("Invalid source square count")
    if not math.isfinite(source_side) or source_side <= 0:
        raise ValueError("Invalid source bounding side")
    k = math.floor(source_side)
    target = source_n + 2 * k + 1
    return target if target <= limit else None


def l_frame_extend(source: Packing, *, clearance: float = 1e-6) -> Packing:
    """Build one actual geometric candidate with two straight strips.

    Source is rebased to its tight axis-aligned bounding box; no known
    best-answer coordinates are hardcoded.
    """
    if not source.squares:
        raise ValueError("An existing packing is required")
    if not math.isfinite(clearance) or not 0 < clearance < 0.01:
        raise ValueError("Clearance must be finite and in (0, 0.01)")
    base = minimum_bounding_square(source.squares)
    side = base.container_side
    k = math.floor(side)
    if k < 1:
        raise ValueError("Source must contain at least one unit square")
    # The earlier squares occupy [0,L]x[0,L]. The new top strip lies
    # above y=L; the right strip lies beyond x=L. Their upper-right
    # corner occupies [L,L+1]x[L,L+1].
    # Keep positive separation from the inherited outer boundary. Exact
    # contacts after float serialization may be uncertifiable with interval
    # SAT, even though the standard float SAT says the layout is valid.
    new_edge = side + 0.5 + clearance
    # The precision validator also rejects exactly touching *adjacent
    # strip squares*, not only contact with the old packing. Borrow a
    # small fraction of the slack L-floor(L) to separate each square.
    fractional_slack = max(0.0, side-k)
    strip_gap = min(clearance, fractional_slack/(2*max(1,k)))
    additional = [Square(i+0.5+i*strip_gap, new_edge, 0.0)
                  for i in range(k)]
    additional += [Square(new_edge, i+0.5+i*strip_gap, 0.0)
                   for i in range(k)]
    additional.append(Square(new_edge, new_edge, 0.0))
    return minimum_bounding_square((*base.squares, *additional))


SPECIAL_30 = tuple(k*k+1 for k in range(2,32))
