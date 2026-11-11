"""Fast geometrical founder for N = 4*m*m + 1, m=1..15.

The arrangement is four identical axis-aligned m*m corner blocks with a
single central unit square rotated 45 degrees. The inward shift follows a
conservative geometric separation calculation rather than repeated O(N^2)
bisection checks. Every stored improvement still passes independent strict
and interval SAT verification in the existing registry.
"""
from __future__ import annotations

import math

from .geometry import Square, Packing, minimum_bounding_square


def four_corner_center_45(n: int, *, spacing: float = 1e-5,
                          safety: float = 1e-5) -> Packing:
    """Generate candidate (not yet validated) with separated contact geometry.

    For the nearest axis-aligned square at (+a,+a) relative to the
    rotated center, separation holds if:
      2*(a-0.5) >= sqrt(2)/2.
    Thus a >= (2+sqrt(2))/4 and max inward shift is
      (2-sqrt(2))/4.
    We subtract strictly positive clearance, and expand the block lattice
    spacing slightly to prevent almost-touching outer squares.
    """
    if type(n) is not int or n < 5 or (n-1) % 4:
        raise ValueError("N must be 4*m*m+1 with m>=1")
    m = math.isqrt((n-1)//4)
    if m < 1 or 4*m*m+1 != n or n > 1000:
        raise ValueError("N must be 4*m*m+1 with 5 <= N <= 1000")
    if not all(math.isfinite(v) and 0 < v < 0.01
               for v in (spacing, safety)):
        raise ValueError("spacing and safety must be finite and in (0,0.01)")
    max_inset = (2-math.sqrt(2))/4
    inset = max_inset - safety
    center = m + 0.5
    squares = []
    for sx in (-1,1):
        for sy in (-1,1):
            for ix in range(m):
                for iy in range(m):
                    rx = (ix+0.5)*(1+spacing)+0.5-inset
                    ry = (iy+0.5)*(1+spacing)+0.5-inset
                    squares.append(Square(center + sx*rx,
                                          center + sy*ry, 0.0))
    squares.append(Square(center, center, math.pi/4))
    return minimum_bounding_square(squares)


SPECIAL_COUNTS = tuple(4*m*m+1 for m in range(1,16))
