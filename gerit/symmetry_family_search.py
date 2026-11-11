"""Small-budget family-preserving geometric search using existing Gerit SAT.

The complete symmetry families use matched group orbits and mirrored/rotated
displacements. Corner families permit an independent fourth corner. All
physical squares retain independent angles in the shared Gerit engine.
Search is heuristic; no claim of optimality follows from its results.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from .geometry import Packing, Square, minimum_bounding_square, validate_packing
from .symmetry_operators import (
    fourfold_seed, vertical_seed, horizontal_seed, diagonal_pairs_seed,
    corner_first_seed, four_corner_cluster_seed,
)


FAMILIES = (
    "fourfold", "vertical_reflection", "horizontal_reflection",
    "diagonal_pairs", "corner_cluster", "three_plus_one",
)
GENERATORS = {
    "fourfold": fourfold_seed,
    "vertical_reflection": vertical_seed,
    "horizontal_reflection": horizontal_seed,
    "diagonal_pairs": diagonal_pairs_seed,
    "corner_cluster": corner_first_seed,
    "three_plus_one": corner_first_seed,
}


@dataclass(frozen=True)
class FamilySearchResult:
    family: str
    n: int
    best: Packing
    initial_side: float
    valid_trials: int
    iterations: int
    improvements: int
    seed: int


def _tight(squares) -> Packing | None:
    p = minimum_bounding_square(tuple(squares))
    return p if validate_packing(p, tolerance=0.0).valid else None


def _release(p: Packing, amount: float) -> Packing | None:
    """Open up free space with a small radial expansion (not fixed packing)."""
    if amount <= 0:
        return p
    cx = sum(s.x for s in p.squares)/len(p.squares)
    cy = sum(s.y for s in p.squares)/len(p.squares)
    factor = 1+amount/max(1.,p.container_side-1)
    return _tight(Square(cx+(s.x-cx)*factor,cy+(s.y-cy)*factor,s.angle)
                  for s in p.squares)


def _symmetry_map(x, y, family):
    if family == "fourfold":
        return ((x,y,0,False),(-y,x,1,False),(-x,-y,2,False),(y,-x,3,False))
    if family == "diagonal_pairs":
        return ((x,y,0,False),(-x,-y,2,False))
    if family == "vertical_reflection":
        return ((x,y,0,False),(-x,y,0,True))
    if family == "horizontal_reflection":
        return ((x,y,0,False),(x,-y,0,True))
    return ((x,y,0,False),)


def _group_orbits(p: Packing, family: str):
    """Identify complete symmetry orbits in the current unmodified geometry."""
    cx = p.container_side/2
    cy = p.container_side/2
    lookup = {(round(s.x-cx, 7),round(s.y-cy, 7)): i
              for i,s in enumerate(p.squares)}
    used = set()
    groups = []
    for idx, sq in enumerate(p.squares):
        if idx in used:
            continue
        x,y = sq.x-cx,sq.y-cy
        orbit = _symmetry_map(x,y,family)
        members = []
        for tx,ty,turn,mirror in orbit:
            j = lookup.get((round(tx,7),round(ty,7)))
            if j is None:
                break
            if j not in [entry[0] for entry in members]:
                members.append((j, turn, mirror))
        else:
            for j,_,_ in members:
                used.add(j)
            groups.append(members)
    return groups


def _rotated(dx,dy,turn):
    for _ in range(turn):
        dx,dy=-dy,dx
    return dx,dy


def _symmetry_move(p: Packing, family: str, rng, step):
    groups = _group_orbits(p, family)
    # A square exactly at the center would be an orbit of one. Its
    # orientation can remain freely rotated by the caller.
    if not groups:
        return None
    chosen = rng.choice(groups)
    anchor = p.squares[chosen[0][0]]
    cx=p.container_side/2
    cy=p.container_side/2
    dx = rng.uniform(-step,step)
    dy = rng.uniform(-step,step)
    da = rng.uniform(-step*.45,step*.45)
    if rng.random()<.7:
        dx += -(anchor.x-cx)*step*rng.uniform(0,.25)
        dy += -(anchor.y-cy)*step*rng.uniform(0,.25)
    values=list(p.squares)
    for j,turn,mirror in chosen:
        mx,my=_rotated(dx,dy,turn)
        if mirror:
            if family=="vertical_reflection":
                mx=-dx
                my=dy
            else:
                mx=dx
                my=-dy
        s=p.squares[j]
        values[j]=Square(s.x+mx,s.y+my,
                         s.angle+(-da if mirror else da))
    return _tight(values)


def _corner_move(p: Packing, family: str, rng, step):
    cx=p.container_side/2
    cy=p.container_side/2
    # Three corners follow one common symmetric offset, while the
    # fourth can move independently for three_plus_one.
    groups={(sx,sy):[] for sx in (-1,1) for sy in (-1,1)}
    for i,s in enumerate(p.squares):
        sx=1 if s.x>=cx else -1
        sy=1 if s.y>=cy else -1
        groups[(sx,sy)].append(i)
    corner = rng.choice(list(groups))
    base_dx=rng.uniform(-step,step)
    base_dy=rng.uniform(-step,step)
    angle=rng.uniform(-step*.25,step*.25)
    positions=list(p.squares)
    if family=="three_plus_one":
        independent = rng.choice(list(groups))
        affected=list(groups) if rng.random()<.45 else [independent]
    else:
        affected=list(groups) if rng.random()<.6 else [corner]
    for key in affected:
        sx,sy=key
        if family=="three_plus_one" and key==independent:
            dx=base_dx*rng.uniform(.6,1.4)
            dy=base_dy*rng.uniform(.6,1.4)
            da=angle*rng.uniform(-1.,1.)
        else:
            dx=sx*base_dx
            dy=sy*base_dy
            da=angle
        for i in groups[key]:
            s=p.squares[i]
            positions[i]=Square(s.x+dx,s.y+dy,s.angle+da)
    return _tight(positions)


def _contract(p: Packing, rng, rate):
    """Move centers inward; check full geometry before adoption."""
    cx = sum(s.x for s in p.squares)/len(p.squares)
    cy = sum(s.y for s in p.squares)/len(p.squares)
    ratio=1-rate
    return _tight(Square(cx+(s.x-cx)*ratio,cy+(s.y-cy)*ratio,s.angle)
                  for s in p.squares)


def initial_family_seed(n: int, family: str, rng) -> Packing:
    if family not in FAMILIES:
        raise ValueError(f"Unknown family: {family}")
    p=GENERATORS[family](n,rng)
    if family=="corner_cluster":
        special=four_corner_cluster_seed(n,rng)
        if special is not None and special.container_side<p.container_side:
            p=special
    if p is None or not validate_packing(p,tolerance=0).valid:
        raise ValueError(f"No valid {family} founder for N={n}")
    return p


def search_family(n: int, family: str, *, seed: int, iterations: int = 200,
                  release: float = .24, report_every: int = 50,
                  progress=None) -> FamilySearchResult:
    if not 2<=n<=1000 or family not in FAMILIES or iterations<0:
        raise ValueError("Invalid family search input")
    if not math.isfinite(release) or not 0<=release<=2:
        raise ValueError("Release must be between 0 and 2")
    if report_every<1:
        raise ValueError("report_every must be positive")
    rng=random.Random(seed)
    base=initial_family_seed(n,family,rng)
    released=_release(base,release)
    working=released if released is not None else base
    best=base
    if working.container_side<best.container_side:
        best=working
    valid=0
    improvements=0
    stale=0
    for i in range(1,iterations+1):
        step=rng.choice((.012,.035,.07,.15)) * max(.22,1-i/(iterations+1))
        kind=rng.random()
        if kind<.2:
            candidate=_contract(working,rng,step*.25)
        elif family in ("corner_cluster","three_plus_one"):
            candidate=_corner_move(working,family,rng,step)
        else:
            candidate=_symmetry_move(working,family,rng,step)
        if candidate is not None:
            valid+=1
            if candidate.container_side<best.container_side-1e-10:
                best=candidate
                improvements+=1
                stale=0
            else:
                stale+=1
            # Gently explore changes that are locally worse; retain best.
            if candidate.container_side <= working.container_side or (
                candidate.container_side < best.container_side + release
                and rng.random()<.12):
                working=candidate
        else:
            stale+=1
        if stale>=max(30,iterations//5):
            working=_release(best, max(.04,release*.4)) or best
            stale=0
        if progress is not None and (i%report_every==0 or i==iterations):
            progress(i,best,valid)
    return FamilySearchResult(family,n,best,base.container_side,
                              valid,iterations,improvements,seed)
