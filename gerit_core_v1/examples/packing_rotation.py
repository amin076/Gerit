"""Rotation-oriented trial moves for the square-packing domain.

No generic optimizer logic belongs in this module. All proposals are validated
against the same legacy strict numerical SAT geometry rules.
"""
import math
from gerit.geometry import Square, minimum_bounding_square, validate_packing


def rotate_probe(parent,rng,intensity,*,cap_margin=0.15,attempts=32):
    """Try an individual square rotation with room-making displacement.

    A broad angle distribution permits non-axis-aligned configurations.
    Proposals may have a worse objective (within cap_margin); the generic
    core's alternative-parent memory determines whether they can be revisited.
    """
    n=len(parent.squares)
    for _ in range(attempts):
        vals=list(parent.squares)
        idx=rng.randrange(n)
        old=vals[idx]
        delta=rng.choice((-1.,1.))*rng.uniform(.035,.55)*max(.5,min(2.,intensity))
        # Move the square as well as rotating it; otherwise dense contact
        # makes the trial invalid before new contacts can be explored.
        xy_scale=rng.choice((.02,.10,.25,.45))*max(.5,min(2.,intensity))
        vals[idx]=Square(old.x+rng.gauss(0,xy_scale),
                         old.y+rng.gauss(0,xy_scale),
                         old.angle+delta)
        candidate=minimum_bounding_square(tuple(vals))
        if candidate.container_side > parent.container_side+cap_margin:
            continue
        if validate_packing(candidate,tolerance=0.).valid:
            return candidate
    return parent


def rotation_statistics(packing,angle_threshold_degrees=1.0):
    """Return orientation diagnostics modulo 90 degrees (true square symmetry)."""
    angles=[]
    for square in packing.squares:
        angle=abs((square.angle+math.pi/4)%(math.pi/2)-math.pi/4)
        angles.append(math.degrees(angle))
    return {"rotated_squares":sum(a>=angle_threshold_degrees for a in angles),
            "max_orientation_degrees":max(angles),
            "angles_degrees":[round(a,5) for a in angles]}
