"""Reproducible population generated from *scratch*, with no prior Gerit genomes.

Constructive lattice/connected seeds plus separate stochastic tilted/scattered
configurations. All supplied positions are explicitly valid before evaluation.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from .connected_tilings import choose_tilings
from .geometry import Packing, Square, minimum_bounding_square, validate_packing
from .selection import packing_distance


@dataclass(frozen=True)
class InitialMember:
    packing: Packing
    source: str


def _random_shape(n: int, rng: random.Random, variant: int) -> Packing:
    """Three stochastic initializers; failures are rejected and retried.

    None of these loads old coordinates or learned weights. Even when the
    reference for rotation is a generated tiling, non-grid poses are new.
    """
    side=math.isqrt(n-1)+1
    mode=variant%3
    if mode==0:  # a whole lattice motif rotated as a rigid assembly
        source=choose_tilings(n,1,seed=rng.randrange(2**30))[0].packing
        alpha=rng.uniform(0.045,0.55)*rng.choice([-1,1])
        scale=rng.uniform(1.008,1.09)
        center_x=sum(s.x for s in source.squares)/n
        center_y=sum(s.y for s in source.squares)/n
        ca,sa=math.cos(alpha),math.sin(alpha)
        squares=tuple(Square(center_x+scale*((s.x-center_x)*ca-(s.y-center_y)*sa),
                             center_y+scale*((s.x-center_x)*sa+(s.y-center_y)*ca),alpha)
                      for s in source.squares)
    elif mode==1:  # independent perturbed centers, slight relative rotations
        source=choose_tilings(n,1,seed=rng.randrange(2**30))[0].packing
        scale=rng.uniform(1.09,1.23)
        cx=sum(s.x for s in source.squares)/n
        cy=sum(s.y for s in source.squares)/n
        squares=tuple(Square(cx+(s.x-cx)*scale+rng.uniform(-0.016,0.016),
                             cy+(s.y-cy)*scale+rng.uniform(-0.016,0.016),
                             rng.uniform(-0.035,0.035)) for s in source.squares)
    else:  # sparse randomized lattice occupancy with true positional novelty
        lattice=side+1 if n <= (side+1)**2 else side+2
        cells=rng.sample([(x,y) for y in range(lattice) for x in range(lattice)],n)
        step=rng.uniform(1.08,1.21)
        squares=tuple(Square((x+.5)*step+rng.uniform(-0.014,0.014),
                             (y+.5)*step+rng.uniform(-0.014,0.014),
                             rng.uniform(-0.045,0.045)) for x,y in cells)
    return minimum_bounding_square(squares)


def make_fresh_population(n_squares: int=12, population: int=25,
                          structural_seeds: int=7, seed: int=2700) -> list[InitialMember]:
    if type(n_squares) is not int or n_squares<2:
        raise ValueError('n_squares must be an integer >= 2')
    if type(population) is not int or population<2:
        raise ValueError('population must be an integer >= 2')
    if type(structural_seeds) is not int or not (1<=structural_seeds<population):
        raise ValueError('structural_seeds must be >=1 and < population')
    rng=random.Random(seed)
    constructed=choose_tilings(n_squares,structural_seeds,seed=seed)
    if not constructed:raise RuntimeError('Missing valid constructive seeds')
    members=[InitialMember(candidate.packing,'connected_tiling') for candidate in constructed]
    # In very small or fully occupied problems, there may be fewer distinct
    # integer-cell arrangements than the requested number of structural slots.
    attempted=0
    while len(members)<population and attempted<max(2000,80*population):
        attempted+=1
        variant=len(members)-len(constructed)+attempted-1
        p=_random_shape(n_squares,rng,variant)
        if not validate_packing(p,tolerance=0.0).valid:continue
        if any(abs(p.container_side-m.packing.container_side)<1e-7 and
               packing_distance(p,m.packing)<1e-5 for m in members):continue
        members.append(InitialMember(p,'random_rotated' if variant%3==0
                                     else 'random_perturbed' if variant%3==1
                                     else 'random_sparse'))
    if len(members)!=population:
        raise RuntimeError(f'Only generated {len(members)}/{population} valid distinct initial solutions')
    assert all(len(m.packing.squares)==n_squares and
               validate_packing(m.packing,tolerance=0.0).valid for m in members)
    return members