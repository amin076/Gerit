"""Gerit phase 1: rigid unit-square geometry, collision and bounds checks."""
from __future__ import annotations
from dataclasses import dataclass
from itertools import combinations
from math import cos, sin, isfinite, isqrt
from typing import Iterable


@dataclass(frozen=True, slots=True)
class Square:
    x: float
    y: float
    angle: float = 0.0  # radians

    def __post_init__(self):
        if not all(isfinite(v) for v in (self.x, self.y, self.angle)):
            raise ValueError("Square position and angle must be finite")


@dataclass(frozen=True, slots=True)
class Packing:
    squares: tuple[Square, ...]
    container_side: float

    def __post_init__(self):
        if not self.squares or not all(isinstance(s, Square) for s in self.squares):
            raise ValueError("Packing requires a nonempty tuple of squares")
        if not isfinite(self.container_side) or self.container_side <= 0:
            raise ValueError("Container side must be finite and positive")


@dataclass(frozen=True, slots=True)
class ValidationResult:
    valid: bool
    overlap_pairs: tuple[tuple[int, int], ...]
    outside_indices: tuple[int, ...]
    tolerance: float


def _tol(t: float) -> float:
    if not isfinite(t) or t < 0:
        raise ValueError("Tolerance must be nonnegative and finite")
    return t


def square_vertices(square: Square) -> tuple[tuple[float, float], ...]:
    """CCW vertices of a rigid unit square, using center and radians."""
    c, s = cos(square.angle), sin(square.angle)
    return tuple((square.x + dx*c-dy*s, square.y + dx*s+dy*c)
                 for dx,dy in ((-.5,-.5),(.5,-.5),(.5,.5),(-.5,.5)))


def _projection(vertices, axis):
    values = tuple(x*axis[0]+y*axis[1] for x,y in vertices)
    return min(values), max(values)


def squares_overlap(a: Square, b: Square, *, tolerance: float = 1e-10) -> bool:
    """SAT interior-overlap check; exact boundary contact is allowed.

    Tolerance may classify penetrations <= tolerance as contact.
    Thus this is a numerical validator, NOT an exact geometric proof.
    """
    _tol(tolerance)
    va, vb = square_vertices(a), square_vertices(b)
    for verts in (va, vb):
        for k in (0, 1):
            x0,y0=verts[k]
            x1,y1=verts[(k+1)%4]
            axis=(-(y1-y0), x1-x0)
            alo,ahi=_projection(va,axis)
            blo,bhi=_projection(vb,axis)
            if min(ahi,bhi)-max(alo,blo) <= tolerance:
                return False
    return True


def square_inside_container(square: Square, side: float, *, tolerance: float = 1e-10) -> bool:
    _tol(tolerance)
    if not isfinite(side) or side <= 0:
        raise ValueError("Container side must be finite and positive")
    return all(-tolerance <= x <= side+tolerance and -tolerance <= y <= side+tolerance
               for x,y in square_vertices(square))


def validate_packing(packing: Packing, *, tolerance: float = 1e-10) -> ValidationResult:
    _tol(tolerance)
    outside=tuple(i for i,s in enumerate(packing.squares)
                  if not square_inside_container(s,packing.container_side,tolerance=tolerance))
    overlap=tuple((i,j) for i,j in combinations(range(len(packing.squares)),2)
                  if squares_overlap(packing.squares[i],packing.squares[j],tolerance=tolerance))
    return ValidationResult(not outside and not overlap, overlap, outside, tolerance)


def minimum_bounding_square(squares: Iterable[Square]) -> Packing:
    """Translate a fixed arrangement to its tight axis-aligned square envelope.

    This does not rearrange squares and cannot fix existing overlaps.
    """
    items=tuple(squares)
    if not items:
        raise ValueError("At least one square is required")
    vertices=[v for s in items for v in square_vertices(s)]
    xmin=min(x for x,y in vertices)
    xmax=max(x for x,y in vertices)
    ymin=min(y for x,y in vertices)
    ymax=max(y for x,y in vertices)
    side=max(xmax-xmin,ymax-ymin)
    return Packing(tuple(Square(s.x-xmin,s.y-ymin,s.angle) for s in items),side)


def unused_area(packing: Packing) -> float:
    if not validate_packing(packing).valid:
        raise ValueError("Packing is invalid; unused area is not meaningful")
    return packing.container_side**2-len(packing.squares)


def grid_baseline(count: int) -> Packing:
    """Valid ceil(sqrt(n)) by ceil(sqrt(n)) row-major starting arrangement."""
    if type(count) is not int or count < 1:
        raise ValueError("count must be a positive integer")
    width=isqrt(count-1)+1
    return Packing(tuple(Square(i%width+.5,i//width+.5) for i in range(count)),float(width))
