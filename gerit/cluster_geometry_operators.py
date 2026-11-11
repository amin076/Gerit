"""Reusable N-agnostic packing geometry proposals: clusters, symmetry escape, insertion.

Only geometry changes live here. Parent selection, fitness, reproduction,
lineage, and historical archive remain in gerit.evolution.
Every emitted packing passes strict zero-tolerance SAT validation.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import random

from .geometry import Packing, Square, minimum_bounding_square, validate_packing, square_vertices


@dataclass(frozen=True)
class OperatorResult:
    name: str
    packing: Packing | None


def _checked(squares, cap: float) -> Packing | None:
    try:
        candidate = minimum_bounding_square(tuple(squares))
    except ValueError:
        return None
    if candidate.container_side > cap + 1e-10:
        return None
    return candidate if validate_packing(candidate, tolerance=0.0).valid else None


def _clusters(parent: Packing, threshold: float = 1.55) -> list[list[int]]:
    """Connected components of near-neighbour square centers."""
    n = len(parent.squares)
    unseen = set(range(n))
    groups = []
    while unseen:
        component = {unseen.pop()}
        frontier = list(component)
        while frontier:
            i = frontier.pop()
            a = parent.squares[i]
            nearby = [j for j in unseen
                      if math.hypot(a.x-parent.squares[j].x,
                                    a.y-parent.squares[j].y) < threshold]
            for j in nearby:
                unseen.remove(j)
                component.add(j)
                frontier.append(j)
        groups.append(sorted(component))
    return groups


def _local_cluster(parent: Packing, rng: random.Random, size: int) -> list[int]:
    """Seeded nearest-neighbour cluster; works even for fully connected grids."""
    n=len(parent.squares)
    anchor=rng.randrange(n)
    x,y=parent.squares[anchor].x,parent.squares[anchor].y
    near=sorted(range(n),key=lambda j:
        (parent.squares[j].x-x)**2+(parent.squares[j].y-y)**2)
    return near[:min(size,n)]


def propose_cluster_compaction(parent: Packing, rng: random.Random,
                               side_cap: float, *, attempts: int = 70) -> Packing | None:
    """Move or rotate a connected local block; allow slight individual relaxation.

    A block can be a whole contact component or nearest-neighbour subset.
    The rigid component is rotated about its own center; members may then
    move independently a small amount. No symmetry requirement is imposed.
    """
    if attempts<1 or len(parent.squares)<2:
        return None
    groups=[c for c in _clusters(parent) if 2<=len(c)<len(parent.squares)]
    best=None
    for _ in range(attempts):
        chosen=(rng.choice(groups) if groups and rng.random()<.35 else
                _local_cluster(parent,rng,rng.randint(2,min(8,len(parent.squares)))))
        cx=sum(parent.squares[i].x for i in chosen)/len(chosen)
        cy=sum(parent.squares[i].y for i in chosen)/len(chosen)
        scale=rng.choice((.004,.018,.06,.14,.30))
        dx=rng.gauss(0,scale)
        dy=rng.gauss(0,scale)
        theta=rng.gauss(0,scale*.33)
        contraction=rng.uniform(-.06,.10)*scale
        cs,sn=math.cos(theta),math.sin(theta)
        values=list(parent.squares)
        for i in chosen:
            sq=parent.squares[i]
            vx,vy=sq.x-cx,sq.y-cy
            values[i]=Square(cx+(1-contraction)*(vx*cs-vy*sn)+dx+
                                  rng.gauss(0,scale*.06),
                             cy+(1-contraction)*(vx*sn+vy*cs)+dy+
                                  rng.gauss(0,scale*.06),
                             sq.angle+theta+rng.gauss(0,scale*.018))
        candidate=_checked(values,side_cap)
        if candidate is not None and (best is None or
                                      candidate.container_side<best.container_side):
            best=candidate
            if candidate.container_side+1e-9<parent.container_side:
                break
    return best


def propose_symmetry_break(parent: Packing, rng: random.Random,
                           side_cap: float, *, attempts: int = 70) -> Packing | None:
    """Perturb one quadrant/cluster without moving its mirrored counterparts.

    This intentionally breaks inherited symmetry. Opposite counterparts are
    not constrained or mirrored. The untouched squares remain valid anchors.
    """
    if attempts<1 or len(parent.squares)<2:
        return None
    center_x=sum(s.x for s in parent.squares)/len(parent.squares)
    center_y=sum(s.y for s in parent.squares)/len(parent.squares)
    choices=[[] for _ in range(4)]
    for i,s in enumerate(parent.squares):
        q=int(s.x>=center_x)+2*int(s.y>=center_y)
        choices[q].append(i)
    best=None
    for _ in range(attempts):
        group=rng.choice([c for c in choices if c])
        if len(group)==len(parent.squares):
            continue
        if rng.random()<.35 and len(group)>2:
            group=rng.sample(group,rng.randint(1,len(group)-1))
        scale=rng.choice((.005,.015,.04,.09,.20))
        dx,dy=rng.gauss(0,scale),rng.gauss(0,scale)
        dtheta=rng.gauss(0,scale*.42)
        gx=sum(parent.squares[i].x for i in group)/len(group)
        gy=sum(parent.squares[i].y for i in group)/len(group)
        cs,sn=math.cos(dtheta),math.sin(dtheta)
        squares=list(parent.squares)
        for i in group:
            s=parent.squares[i]
            x,y=s.x-gx,s.y-gy
            squares[i]=Square(gx+x*cs-y*sn+dx+rng.gauss(0,scale*.025),
                              gy+x*sn+y*cs+dy+rng.gauss(0,scale*.025),
                              s.angle+dtheta+rng.gauss(0,scale*.025))
        p=_checked(squares,side_cap)
        if p is not None and (best is None or p.container_side<best.container_side):
            best=p
            if p.container_side+1e-9<parent.container_side:
                break
    return best


def propose_incremental_insertion(source: Packing, rng: random.Random,
                                  target_n: int, side_cap: float,
                                  *, attempts: int = 350) -> Packing | None:
    """Insert missing squares into a valid smaller packing, with collective relaxation.

    Not an ordinary same-N mutation: this is a constructive founder generator.
    Multiple expansion factors, axial shifts and candidate positions are sampled.
    No published packing coordinates are used. Failure is explicit (None).
    """
    if target_n<len(source.squares) or attempts<1:
        return None
    if not validate_packing(source,tolerance=0.0).valid:
        raise ValueError("Insertion source must be strictly valid")
    if target_n==len(source.squares):
        return source if source.container_side<=side_cap else None
    best=None
    side=source.container_side
    center=side/2
    missing=target_n-len(source.squares)
    for trial in range(attempts):
        # Increasing the source layout can free insertion corridors, but
        # any resulting side must remain within the exploration cap.
        factor=rng.choice((1.,1.015,1.035,1.065,1.10,1.15))
        angle_noise=rng.choice((0.,0.,.008,.025))
        jitter=rng.choice((0.,.004,.015))
        squares=[
            Square(center+(s.x-center)*factor+rng.gauss(0,jitter),
                   center+(s.y-center)*factor+rng.gauss(0,jitter),
                   s.angle+rng.gauss(0,angle_noise))
            for s in source.squares]
        base=_checked(squares,side_cap)
        if base is None:
            continue
        current=list(base.squares)
        ok=True
        for added in range(missing):
            # Try likely gaps and a broad randomized scan in the enclosing
            # square. The new square's orientation is not prescribed.
            candidates=[]
            for i in range(45):
                if i<20:
                    k=rng.randrange(len(current))
                    t=current[k]
                    direction=rng.randrange(8)
                    phi=direction*math.pi/4
                    radius=rng.uniform(1.005,1.75)
                    x=t.x+radius*math.cos(phi)
                    y=t.y+radius*math.sin(phi)
                else:
                    x=rng.uniform(.5,side_cap-.5)
                    y=rng.uniform(.5,side_cap-.5)
                angle=rng.choice((0.,0.,rng.uniform(-math.pi/4,math.pi/4)))
                proposed=_checked([*current,Square(x,y,angle)],side_cap)
                if proposed is not None:
                    candidates.append(proposed)
            if not candidates:
                ok=False
                break
            chosen=min(candidates,key=lambda p:p.container_side)
            current=list(chosen.squares)
        if ok:
            p=_checked(current,side_cap)
            if p is not None and (best is None or p.container_side<best.container_side):
                best=p
    return best


def build_incremental_founder(n: int, rng: random.Random, cap: float,
                              *, sources: tuple[Packing,...],
                              attempts: int = 260) -> Packing | None:
    """Build a target-N founder from one of several smaller-N geometries."""
    valid_sources=[p for p in sources if len(p.squares)<n and
                   validate_packing(p,tolerance=0.0).valid]
    if not valid_sources:
        return None
    best=None
    for source in valid_sources:
        p=propose_incremental_insertion(source,rng,n,cap,attempts=attempts)
        if p is not None and (best is None or p.container_side<best.container_side):
            best=p
    return best
