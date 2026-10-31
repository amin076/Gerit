"""Conservative numerical local compression of nonoverlapping unit squares."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from math import cos, sin
from random import Random
from .geometry import Packing, Square, minimum_bounding_square, validate_packing, square_vertices

@dataclass(frozen=True)
class CompressionSettings:
    attempts_per_child: int = 35
    translation_scales: tuple[float,...] = (0.035, 0.012, 0.004)
    rotation_scales: tuple[float,...] = (0.05, 0.016, 0.005)
    group_move_probability: float = 0.35
    global_shrink_probability: float = 0.20
    improvement_epsilon: float = 1e-10

def _tight_bounds(squares: tuple[Square,...]):
    vertices = [v for s in squares for v in square_vertices(s)]
    return (min(x for x,y in vertices), max(x for x,y in vertices),
            min(y for x,y in vertices), max(y for x,y in vertices))

def _score(p: Packing) -> tuple[float,float]:
    x0,x1,y0,y1 = _tight_bounds(p.squares)
    return p.container_side, (x1-x0)+(y1-y0)

def compress_valid(child: Packing, rng: Random,
                   settings: CompressionSettings = CompressionSettings(),
                   side_cap: float = 3.0, *,
                   validation_tolerance: float = 0.0) -> tuple[Packing,dict]:
    """Compress a child with strict full-packing checks; never accept worse L.

    Moves are candidate endpoint states, NOT collision-free physical trajectories.
    Equal-L changes are accepted only when width+height decreases.
    """
    if not validate_packing(child,tolerance=validation_tolerance).valid:
        raise ValueError("Compression input must be valid")
    current = child
    rebased = minimum_bounding_square(child.squares)
    if validate_packing(rebased,tolerance=validation_tolerance).valid:
        current = rebased
    original_side = current.container_side
    accepted = 0
    checks = 0
    for trial in range(settings.attempts_per_child):
        n = len(current.squares)
        phase = trial // max(1,settings.attempts_per_child//len(settings.translation_scales))
        j = min(len(settings.translation_scales)-1,phase)
        sigma_xy = settings.translation_scales[j]
        sigma_a = settings.rotation_scales[j]
        values = list(current.squares)
        roll = rng.random()
        if roll < settings.global_shrink_probability:
            cx = sum(s.x for s in values)/n
            cy = sum(s.y for s in values)/n
            factor = 1-rng.uniform(.001,2*sigma_xy)
            values = [Square(cx+(s.x-cx)*factor,cy+(s.y-cy)*factor,s.angle)
                      for s in values]
        elif roll < settings.global_shrink_probability+settings.group_move_probability:
            count = min(n,rng.choice([2,2,3,n])) if n>=2 else 1
            indices = rng.sample(range(n),count)
            dx,dy,da = rng.gauss(0,sigma_xy),rng.gauss(0,sigma_xy),rng.gauss(0,sigma_a)
            cx = sum(values[i].x for i in indices)/len(indices)
            cy = sum(values[i].y for i in indices)/len(indices)
            c,s = cos(da),sin(da)
            for i in indices:
                old = values[i]
                rx,ry = old.x-cx,old.y-cy
                values[i] = Square(cx+rx*c-ry*s+dx,cy+rx*s+ry*c+dy,old.angle+da)
        else:
            x0,x1,y0,y1 = _tight_bounds(current.squares)
            scores = []
            for sq in values:
                v=square_vertices(sq)
                xs=[x for x,y in v];ys=[y for x,y in v]
                gap=min(min(xs)-x0,x1-max(xs),min(ys)-y0,y1-max(ys))
                scores.append(1.0/(.02+max(0.,gap)))
            index = rng.choices(range(n),weights=scores,k=1)[0]
            old = values[index]
            center_x = (x0+x1)/2
            center_y = (y0+y1)/2
            drift = .6*sigma_xy
            nx = old.x+rng.gauss(0,sigma_xy)+(drift if old.x<center_x else -drift)
            ny = old.y+rng.gauss(0,sigma_xy)+(drift if old.y<center_y else -drift)
            values[index] = Square(nx,ny,old.angle+rng.gauss(0,sigma_a))
        proposed = minimum_bounding_square(tuple(values))
        checks += 1
        if proposed.container_side > min(side_cap,current.container_side)+settings.improvement_epsilon:
            continue
        if not validate_packing(proposed,tolerance=validation_tolerance).valid:
            continue
        old_score,new_score = _score(current),_score(proposed)
        if (new_score[0] < old_score[0]-settings.improvement_epsilon
            or (abs(new_score[0]-old_score[0])<=settings.improvement_epsilon
                and new_score[1] < old_score[1]-settings.improvement_epsilon)):
            current = proposed
            accepted += 1
    # Safeguard floating-point contact configurations from repeated rebasing.
    if not validate_packing(current,tolerance=validation_tolerance).valid:
        current = child
    assert validate_packing(current,tolerance=validation_tolerance).valid
    assert current.container_side<=original_side+settings.improvement_epsilon
    return current,{
        "compression_trials":checks,
        "compression_accepted":accepted,
        "compression_delta_side":original_side-current.container_side,
        "compression_side_before":original_side,
        "compression_side_after":current.container_side,
        "compression_method":"local_group_and_boundary_coordinate_search",
        "compression_settings":asdict(settings)
    }
