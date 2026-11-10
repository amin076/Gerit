"""Five-square structural search: four corner squares plus a rotating center.

A complementary coordinated operator for Gerit, NOT a replacement for the
generic evolutionary solver. Every proposed packing is checked with Gerit's
existing SAT geometry. The center starts unrotated in a 3x3 container.
"""
from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass

from gerit.geometry import Square, Packing, minimum_bounding_square, validate_packing

N = 5
BASELINE_SIDE = 3.0
MAX_ROTATION = math.pi / 4
SAFETY_MARGIN = 2e-7


def corner_center_seed() -> Packing:
    """Exactly four axis-aligned corner squares and one at the center, L=3."""
    return minimum_bounding_square((
        Square(0.5, 0.5), Square(2.5, 0.5),
        Square(0.5, 2.5), Square(2.5, 2.5),
        Square(1.5, 1.5),
    ))


def arrangement(angle: float, inward: float) -> Packing:
    """Move four corners inward together while independently rotating center."""
    if not (math.isfinite(angle) and math.isfinite(inward)):
        raise ValueError("angle and inward must be finite")
    if not (0 <= angle <= MAX_ROTATION and 0 <= inward <= 0.25):
        raise ValueError("angle or inward outside search domain")
    return minimum_bounding_square((
        Square(0.5+inward, 0.5+inward),
        Square(2.5-inward, 0.5+inward),
        Square(0.5+inward, 2.5-inward),
        Square(2.5-inward, 2.5-inward),
        Square(1.5, 1.5, angle),
    ))


def best_inward_for_angle(angle: float, *, iterations: int = 47) -> tuple[Packing,float]:
    """Bisection for feasible coordinated contraction at a given angle.

    Geometry is validated on every step. A conservative clearance is retained
    to avoid claiming near-contact solutions that are numerically ambiguous.
    """
    if not (math.isfinite(angle) and 0 <= angle <= MAX_ROTATION):
        raise ValueError("angle outside [0,pi/4]")
    low, high = 0., 0.25
    for _ in range(iterations):
        mid = (low+high)/2
        trial = arrangement(angle, mid)
        if validate_packing(trial, tolerance=0.0).valid:
            low = mid
        else:
            high = mid
    safe = max(0., low-SAFETY_MARGIN)
    result = arrangement(angle, safe)
    if not validate_packing(result,tolerance=0.0).valid:
        raise RuntimeError("Conservative candidate failed geometry")
    return result,safe


@dataclass(frozen=True)
class ExperimentResult:
    seed: int
    proposals: int
    accepted_improvements: int
    best_angle: float
    best_inward: float
    best: Packing
    trace: tuple[dict, ...]


def search(*, seed: int=2715, proposals: int=300) -> ExperimentResult:
    """Multi-move seeded search with occasional random restarts and mutations.

    The angle starts at ZERO and is changed by perturbations. For each angle,
    a *joint* corner contraction is optimized by geometric feasibility checks.
    This is a deliberately small, interpretable specialist search baseline.
    """
    if type(proposals) is not int or proposals < 1:
        raise ValueError("proposals must be a positive integer")
    rng = random.Random(seed)
    best = corner_center_seed()
    best_angle = 0.
    best_inward = 0.
    current_angle = 0.
    accepted=0
    trace = [{"step":0,"angle":0.,"inward":0.,"best_side":3.,"kind":"seed"}]
    for step in range(1,proposals+1):
        if step % 11 == 0:
            angle=rng.uniform(0, MAX_ROTATION)  # diverse restart
            kind="restart"
        else:
            angle=min(MAX_ROTATION,max(0.,current_angle+rng.gauss(0.,0.15)))
            kind="coordinated_mutation"
        candidate,inward=best_inward_for_angle(angle)
        if candidate.container_side < best.container_side-1e-11:
            best,best_angle,best_inward=candidate,angle,inward
            accepted+=1
            current_angle=angle
            trace.append({"step":step,"angle":angle,"inward":inward,
                          "best_side":best.container_side,"kind":kind})
        elif rng.random()<0.15:
            current_angle=angle
    assert validate_packing(best,tolerance=0.0).valid
    return ExperimentResult(seed,proposals,accepted,best_angle,best_inward,
                            best,tuple(trace))


def to_json(result: ExperimentResult) -> dict:
    packing=result.best
    return {
        "status":"completed",
        "method":"coordinated_center_rotation_plus_four_corner_contraction",
        "initialization":"four_corners_plus_center_at_zero_rotation",
        "seed":result.seed,"proposals":result.proposals,
        "accepted_improvements":result.accepted_improvements,
        "initial_side":BASELINE_SIDE,
        "best_angle":result.best_angle,
        "best_inward":result.best_inward,
        "best":{"side":packing.container_side,
                "squares":[asdict(s) for s in packing.squares]},
        "trace":list(result.trace),
    }
