"""Contact-aware coordinated endpoint moves for unit-square packing.

Proposals use support distances to put one or two squares near an *existing*
unit-square edge. Only the final endpoint is tested; no continuous path is
assumed. This operator neither loads a known packing nor inserts a grid.
"""
from __future__ import annotations

import math
import random

from . import adaptive_v3 as adaptive
from .geometry import Packing, Square, minimum_bounding_square


def propose_contact_relocate(parent: Packing, rng: random.Random,
                             side_cap: float, *, attempts: int = 40):
    """Relocate 1-2 squares against fixed or newly placed anchor edges.

    The normal support projection of two rotated unit squares sets a strictly
    nonpenetrating contact gap *for that pair*. Other squares and the square
    container are checked using the shared strict SAT geometry validator.
    """
    n = len(parent.squares)
    if n < 2 or side_cap < 1.0 or attempts < 1:
        return None, {**adaptive._meta(adaptive.STRUCTURAL,parent,False,max(0,attempts),idx=2),
                      'move_strategy':'contact_guided', 'moved_squares':0}
    original = parent.squares
    for attempt in range(1,attempts+1):
        count = min(n-1, rng.choice((1,1,1,2,2)))
        moving = rng.sample(range(n),count)
        # The original positions of moved squares must *not* serve as anchors.
        fixed = [i for i in range(n) if i not in moving]
        placed = list(fixed)
        values = list(original)
        for i in moving:
            anchor = values[rng.choice(placed)]
            normal_angle = anchor.angle + rng.randrange(4)*math.pi/2
            u = (math.cos(normal_angle),math.sin(normal_angle))
            t = (-u[1],u[0])
            # Nearby parallel and *genuinely relatively rotated* poses.
            delta = rng.choice((0.,0.,-.015,.015,-.045,.045,-.08,.08))
            angle = anchor.angle + delta if rng.random() < .80 else original[i].angle
            # Support of a unit square along an anchor-aligned normal.
            half_support = .5*(abs(math.cos(angle-normal_angle))+
                                abs(math.sin(angle-normal_angle)))
            gap = rng.choice((1e-6,1e-4,.003,.015))
            tangent_offset = rng.uniform(-.42,.42)
            distance = .5 + half_support + gap
            values[i] = Square(anchor.x+distance*u[0]+tangent_offset*t[0],
                               anchor.y+distance*u[1]+tangent_offset*t[1],angle)
            placed.append(i)
        candidate = minimum_bounding_square(tuple(values))
        if candidate.container_side>side_cap+1e-10:continue
        if not adaptive.validate_packing(candidate,tolerance=0.0).valid:continue
        meta=adaptive._meta(adaptive.STRUCTURAL,parent,True,attempt,idx=2)
        meta.update(move_strategy='contact_guided',moved_squares=count,
                    relative_tilt_proposed=any(abs(values[i].angle-original[i].angle)>1e-4
                                               for i in moving))
        return candidate,meta
    meta=adaptive._meta(adaptive.STRUCTURAL,parent,False,attempts,idx=2)
    meta.update(move_strategy='contact_guided',moved_squares=0)
    return None,meta