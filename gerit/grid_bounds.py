"""Constructive grid bounds and safe search caps for unit-square packing.

ceil(sqrt(n)) is a *known feasible upper bound* on the minimum side; it
is not the area lower bound sqrt(n), nor an obligatory cap on mutations.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from math import isqrt, sqrt, isfinite
from collections.abc import Iterable
from .geometry import grid_baseline, validate_packing

@dataclass(frozen=True)
class GridBounds:
    squares: int
    area_lower_side: float
    grid_upper_side: int
    grid_columns: int
    grid_rows: int
    spare_cells: int

    def to_dict(self):
        return asdict(self)


def grid_bounds(count: int) -> GridBounds:
    if type(count) is not int or count < 1:
        raise ValueError('square count must be a positive integer')
    width = isqrt(count - 1) + 1
    return GridBounds(count, sqrt(count), width, width,
                      (count + width - 1) // width, width**2 - count)


def automatic_search_cap(sides: Iterable[float], square_count: int,
                         margin: float = 0.15) -> float:
    """Allow all imported parents AND exploratory temporary worsening.

    The cap is intentionally allowed to exceed a known grid feasible bound.
    Setting it exactly to ceil(sqrt(n)) would exclude any parent larger than
    that grid, which is precisely what 12-square v4 continuation imports.
    """
    if not isfinite(margin) or margin < 0:
        raise ValueError('margin must be non-negative and finite')
    values = tuple(float(v) for v in sides)
    if not values or not all(isfinite(v) and v > 0 for v in values):
        raise ValueError('input parent sides must be finite positive numbers')
    return max(float(grid_bounds(square_count).grid_upper_side), max(values)) + margin


def checked_grid(count: int):
    """Optional explicit baseline constructor. NEVER injected implicitly."""
    result = grid_baseline(count)
    if not validate_packing(result, tolerance=0.0).valid:
        raise RuntimeError('constructed grid is not geometrically valid')
    return result