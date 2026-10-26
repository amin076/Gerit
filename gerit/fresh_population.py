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


def _random_shape(n: int, rng: random.Random, variant: int,
                  structural_options: tuple[Packing, ...]) -> Packing:
    """Three stochastic initializers; failures are rejected and retried.

    None of these loads old coordinates or learned weights. Even when the
    reference for rotation is a generated tiling, non-grid poses are new.
    """
    side=math.isqrt(n-1)+1
    # Each six fresh stochastic slots include 3 close-to-frontier rigid
    # rotations, 2 individually tilted configurations and 1 broad explorer.
    # A retry must not silently change the intended slot's family.
    mode=0 if variant%6 in (0,1,2) else (1 if variant%6 in (3,4) else 2)
    if mode==0:  # two differently oriented subgroups, NOT rigid rotation of the whole packing
        source=rng.choice(structural_options)
        # Rigidly rotating *all* unit squares together leaves every relative
        # angle at zero and adds no genuine orientational diversity. Split
        # centers into two spatial groups and give the groups opposite tilts.
        axis=rng.choice(('x','y'))
        order=sorted(range(n),key=lambda i:((source.squares[i].x if axis=='x'
                                               else source.squares[i].y),
                                              source.squares[i].x,source.squares[i].y))
        group=set(order[:n//2])
        direction=rng.choice((-1.,1.))
        a=direction*rng.uniform(.028,.062)
        b=-direction*rng.uniform(.022,.057)
        # A small uniform expansion makes the new relative angles feasible
        # without using inherited poses or optimization history.
        scale=1+1.24*max(abs(a),abs(b))+rng.uniform(.005,.016)
        cx=sum(s.x for s in source.squares)/n
        cy=sum(s.y for s in source.squares)/n
        squares=tuple(Square(cx+(s.x-cx)*scale,cy+(s.y-cy)*scale,
                             a if i in group else b)
                      for i,s in enumerate(source.squares))
    elif mode==1:  # true independent angles, with nonuniform local center jitter
        source=rng.choice(structural_options)
        angles=[rng.uniform(-.055,.055) for _ in source.squares]
        scale=1+1.28*max(abs(a) for a in angles)+rng.uniform(.010,.022)
        cx=sum(s.x for s in source.squares)/n
        cy=sum(s.y for s in source.squares)/n
        squares=tuple(Square(cx+(s.x-cx)*scale+rng.uniform(-.005,.005),
                             cy+(s.y-cy)*scale+rng.uniform(-.005,.005),a)
                      for s,a in zip(source.squares,angles))
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
    # More than one constructive silhouette must underpin independent random
    # poses. The old constructor inadvertently rotated/perturbed ONLY the
    # canonical lattice, and most candidates started too far above grid L.
    diverse_shapes=choose_tilings(n_squares,max(structural_seeds,12),seed=seed+31337)
    structural_options=tuple(item.packing for item in diverse_shapes)
    # In very small or fully occupied problems, there may be fewer distinct
    # integer-cell arrangements than the requested number of structural slots.
    attempted=0
    while len(members)<population and attempted<max(2000,80*population):
        attempted+=1
        variant=(len(members)-len(constructed))%6
        p=_random_shape(n_squares,rng,variant,structural_options)
        if not validate_packing(p,tolerance=0.0).valid:continue
        if any(abs(p.container_side-m.packing.container_side)<1e-7 and
               packing_distance(p,m.packing)<1e-5 for m in members):continue
        members.append(InitialMember(p,'random_rotated' if variant in (0,1,2)
                                     else 'random_perturbed' if variant in (3,4)
                                     else 'random_sparse'))
    if len(members)!=population:
        raise RuntimeError(f'Only generated {len(members)}/{population} valid distinct initial solutions')
    assert all(len(m.packing.squares)==n_squares and
               validate_packing(m.packing,tolerance=0.0).valid for m in members)
    return members