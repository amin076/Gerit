"""Exact-in-angle rigid global rotation for a fixed collection of squares.

The optimizer changes only the common world-frame orientation, never relative
square positions or relative angles. It uses the convex hull of all vertices,
partitions angles at support-vertex switches, and evaluates every stationary
point and width/height crossover inside each interval. Numerical floating
point output is not a formal proof of geometric exactness.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, pi, sin
from typing import Iterable

from .geometry import Packing, Square, minimum_bounding_square, square_vertices


@dataclass(frozen=True)
class RotationResult:
    packing: Packing
    angle_radians: float
    side_before: float
    side_after: float
    candidate_angles: int


def _hull(points: Iterable[tuple[float, float]]) -> tuple[tuple[float, float], ...]:
    pts = sorted(set(points))
    if len(pts) <= 1:
        return tuple(pts)

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return tuple(lower[:-1] + upper[:-1])


def _rotated_point(point, angle):
    c, s = cos(angle), sin(angle)
    x, y = point
    return x * c - y * s, x * s + y * c


def optimal_global_rotation(packing: Packing) -> RotationResult:
    """Find global minimum bounding-square side over all rigid rotations.

    Square-envelope symmetry reduces the search to [0, pi/2]. On each
    angular interval with unchanged extreme hull vertices, W and H are
    sinusoidal. The minimum of max(W,H) occurs at a boundary, a W/H
    crossover, or a stationary point of the active sinusoid.
    """
    points = [v for sq in packing.squares for v in square_vertices(sq)]
    hull = _hull(points)
    period = pi / 2
    breaks = [0.0, period]

    # Changes of supporting hull vertices occur exactly when an edge
    # becomes perpendicular to the respective coordinate projection.
    for a, b in zip(hull, hull[1:] + hull[:1]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        if dx == 0.0 and dy == 0.0:
            continue
        for theta in (atan2(dx, dy), atan2(-dy, dx)):
            t = theta % period
            if 1e-12 < t < period - 1e-12:
                breaks.append(t)
    breaks.sort()
    unique_breaks = []
    for t in breaks:
        if not unique_breaks or t - unique_breaks[-1] > 1e-11:
            unique_breaks.append(t)
    if unique_breaks[-1] < period:
        unique_breaks.append(period)

    candidates = list(unique_breaks)
    for lo, hi in zip(unique_breaks, unique_breaks[1:]):
        if hi - lo < 1e-12:
            continue
        mid = (lo + hi) / 2
        transformed = [_rotated_point(p, mid) for p in hull]
        ir = max(range(len(hull)), key=lambda i: transformed[i][0])
        il = min(range(len(hull)), key=lambda i: transformed[i][0])
        it = max(range(len(hull)), key=lambda i: transformed[i][1])
        ib = min(range(len(hull)), key=lambda i: transformed[i][1])
        xr, yr = hull[ir]
        xl, yl = hull[il]
        xt, yt = hull[it]
        xb, yb = hull[ib]
        # Width = A*cos(t)+B*sin(t), Height = C*cos(t)+D*sin(t).
        A, B = xr - xl, -(yr - yl)
        C, D = yt - yb, xt - xb
        for kind, u, v in ((0, A, B), (0, C, D), (1, A - C, B - D)):
            if abs(u) + abs(v) < 1e-14:
                continue
            # Derivative zero: -u*sin(t) + v*cos(t) = 0.
            # Equality zero: u*cos(t) + v*sin(t) = 0.
            base = atan2(v, u) if kind == 0 else atan2(-u, v)
            for k in range(-2, 4):
                theta = base + k * pi
                if lo < theta < hi:
                    candidates.append(theta)

    best = None
    best_theta = 0.0
    for theta in candidates:
        q = [_rotated_point(p, theta) for p in hull]
        xs = [v[0] for v in q]
        ys = [v[1] for v in q]
        L = max(max(xs) - min(xs), max(ys) - min(ys))
        if best is None or L < best:
            best, best_theta = L, theta

    # Rotating about the origin preserves all pairwise distances and angles.
    c, s = cos(best_theta), sin(best_theta)
    transformed_squares = tuple(
        Square(sq.x * c - sq.y * s, sq.x * s + sq.y * c,
               sq.angle + best_theta)
        for sq in packing.squares
    )
    result = minimum_bounding_square(transformed_squares)
    # Avoid degrading near-ties because of floating-point operations.
    original = minimum_bounding_square(packing.squares)
    if result.container_side > original.container_side + 1e-10:
        return RotationResult(original, 0.0, packing.container_side,
                              original.container_side, len(candidates))
    return RotationResult(result, best_theta, packing.container_side,
                          result.container_side, len(candidates))
