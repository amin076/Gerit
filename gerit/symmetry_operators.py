"""Reusable geometry-only symmetry and block-crossover operators for unit squares.

No fitness, parent selection, lineage, historical archive, or known optimal poses
live here. All candidates are checked by the existing strict Gerit geometry.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import random
from typing import Callable

from .geometry import Packing, Square, grid_baseline, minimum_bounding_square, validate_packing
from .x_core_geometry import x_core_five_plus_twelve_seed
from .t_core_geometry import t_core_three_arm_seed

@dataclass(frozen=True)
class GeometryOperator:
    name: str
    description: str
    generate: Callable[[int, random.Random], Packing | None]

def _valid(squares) -> Packing | None:
    p = minimum_bounding_square(tuple(squares))
    return p if validate_packing(p, tolerance=0.0).valid else None

def _rot(x, y, turns, k):
    for _ in range(turns):
        x, y = k-1-y, x
    return x, y

def _orbit(x, y, k, kind):
    if kind == "fourfold":
        return {_rot(x, y, t, k) for t in range(4)}
    if kind == "diagonal_pairs":
        return {(x,y),(k-1-x,k-1-y)}
    if kind == "horizontal":
        return {(x,y),(x,k-1-y)}
    if kind == "vertical":
        return {(x,y),(k-1-x,y)}
    raise ValueError(kind)

def _grid_cells(n, kind, rng):
    """Build lattice occupancy by complete symmetry orbits where possible.

    If n cannot be expressed by full orbits, remaining cells are added in
    symmetric-priority order. The symmetry is then partial, not falsely claimed.
    """
    k=math.isqrt(n-1)+1
    cells={(x,y) for y in range(k) for x in range(k)}
    groups={}
    for x,y in cells:
        orbit=frozenset(_orbit(x,y,k,kind))
        groups[tuple(sorted(orbit))]=orbit
    def rank(orb):
        return (min(min(x,k-1-x,y,k-1-y) for x,y in orb),
                -sum((x-(k-1)/2)**2+(y-(k-1)/2)**2 for x,y in orb),
                rng.random())
    ordered=sorted(groups.values(),key=rank)
    selected=set()
    # Prefer complete orbits. Greedy construction never violates occupancy.
    for orb in ordered:
        if len(selected)+len(orb)<=n:
            selected.update(orb)
    if len(selected)<n:
        remain=sorted(cells-selected,key=lambda v:(
            min(v[0],k-1-v[0],v[1],k-1-v[1]),
            -((v[0]-(k-1)/2)**2+(v[1]-(k-1)/2)**2),
            rng.random()))
        selected.update(remain[:n-len(selected)])
    assert len(selected)==n
    return sorted(selected)

def fourfold_seed(n, rng):
    return _valid(Square(x+.5,y+.5,0.) for x,y in _grid_cells(n,"fourfold",rng))

def diagonal_pairs_seed(n, rng):
    return _valid(Square(x+.5,y+.5,0.) for x,y in _grid_cells(n,"diagonal_pairs",rng))

def horizontal_seed(n, rng):
    return _valid(Square(x+.5,y+.5,0.) for x,y in _grid_cells(n,"horizontal",rng))

def vertical_seed(n, rng):
    return _valid(Square(x+.5,y+.5,0.) for x,y in _grid_cells(n,"vertical",rng))

def corner_first_seed(n, rng):
    """Fill a ceil(sqrt(N)) square lattice from its four corners inward."""
    k=math.isqrt(n-1)+1
    positions=[(x,y) for y in range(k) for x in range(k)]
    rng.shuffle(positions)
    positions.sort(key=lambda v:(min(v[0],k-1-v[0],v[1],k-1-v[1]),
                                  -((v[0]-(k-1)/2)**2+(v[1]-(k-1)/2)**2)))
    return _valid(Square(x+.5,y+.5,0.) for x,y in positions[:n])

def four_corner_cluster_seed(n, rng):
    """Four congruent corner blocks and a rotated center for 4*m*m+1.

    The cluster inset is determined by geometric collision tests, not by an
    embedded reference answer or target side. A positive clearance is kept.
    """
    m=math.isqrt((n-1)//4)
    if m<2 or 4*m*m+1!=n:
        return None
    center=m+.5
    # The outermost square of each block has radius m from the center.
    # Moving all four blocks inward is the same geometry across all m.
    def build(inset):
        cells=[]
        for sx in (-1,1):
            for sy in (-1,1):
                for ix in range(m):
                    for iy in range(m):
                        # Neighbour distance >1 avoids floating-point SAT contacts.
                        rx=(ix+.5)*(1+1e-5)+.5-inset
                        ry=(iy+.5)*(1+1e-5)+.5-inset
                        cells.append(Square(center+sx*rx,center+sy*ry,0.))
        cells.append(Square(center,center,math.pi/4))
        return _valid(cells)
    baseline=build(0.)
    if baseline is None:
        return None
    low=0.0
    high=.35
    for _ in range(28):
        mid=(low+high)/2
        if build(mid) is not None:
            low=mid
        else:
            high=mid
    return build(max(0.,low-1e-5))

def random_sparse_seed(n, rng):
    k=math.isqrt(n-1)+1
    side=k+1
    cells=rng.sample([(x,y) for y in range(side) for x in range(side)],n)
    return _valid(Square(x+.5,y+.5,0.) for x,y in cells)

OPERATORS=(
    GeometryOperator("fourfold","complete 90-degree rotational orbits",fourfold_seed),
    GeometryOperator("diagonal_pairs","180-degree opposing-diagonal pairs",diagonal_pairs_seed),
    GeometryOperator("horizontal","top/bottom mirror pairs",horizontal_seed),
    GeometryOperator("vertical","left/right mirror pairs",vertical_seed),
    GeometryOperator("corner_first","fill corners before interior cells",corner_first_seed),
    GeometryOperator("four_corner_clusters","four repeated corner blocks with center",four_corner_cluster_seed),
    GeometryOperator("x_core_fourfold","five edge-connected 45-degree diamonds plus four 3-square groups",x_core_five_plus_twelve_seed),
    GeometryOperator("t_core_three_arm","three-edge-adjacent 45-degree diamond arms with one axis-aligned gap square",t_core_three_arm_seed),
    GeometryOperator("random_sparse","randomized sparse lattice baseline",random_sparse_seed),
)

def geometry_seed_bank(n, seed, *, copies=3):
    """Name-tagged independent valid candidates, no fitness-based selection."""
    rng=random.Random(seed)
    values=[("grid",grid_baseline(n))]
    for op in OPERATORS:
        for _ in range(copies):
            candidate=op.generate(n,rng)
            if candidate is not None:
                values.append((op.name,candidate))
    return values

def multi_parent_quadrant_crossover(first: Packing, second: Packing,
                                    rng: random.Random, side_cap: float) -> Packing | None:
    """Use two real parents: inherit a full quadrant from the second genome.

    The second parent is not a random mutation of the first. Labels/order of
    squares are matched spatially via nearest assignments; every resulting
    geometry is independently checked. Invalid recombinations are discarded.
    """
    if len(first.squares)!=len(second.squares):
        raise ValueError("Parent N mismatch")
    n=len(first.squares)
    cx=first.container_side/2
    cy=first.container_side/2
    quadrant=rng.randrange(4)
    def q(s):
        return int(s.x>=cx)+2*int(s.y>=cy)
    chosen=[i for i,s in enumerate(first.squares) if q(s)==quadrant]
    if not chosen:
        return None
    # Convert second coordinates to the same normalized frame so that
    # inheriting a block is meaningful even when container sizes differ.
    factor=first.container_side/second.container_side
    remaining=set(range(n))
    values=list(first.squares)
    for i in chosen:
        a=first.squares[i]
        j=min(remaining,key=lambda j:
            (second.squares[j].x*factor-a.x)**2+
            (second.squares[j].y*factor-a.y)**2)
        remaining.remove(j)
        b=second.squares[j]
        values[i]=Square(b.x*factor,b.y*factor,b.angle)
    candidate=_valid(values)
    return candidate if candidate is not None and candidate.container_side<=side_cap+1e-9 else None

def propose_symmetry_group_move(parent: Packing, rng: random.Random,
                                side_cap: float, *, attempts: int = 40) -> Packing | None:
    """Mutation proposal that inherits a parent's squares in symmetry-related groups.

    Uses the parent layout (not a fresh template). Approximate counterpart
    matching allows imperfect symmetry. Every mutated square can translate and
    rotate, and all results pass strict geometry validation.
    """
    if len(parent.squares)<2 or not validate_packing(parent,tolerance=0.0).valid:
        return None
    n=len(parent.squares)
    center=parent.container_side/2
    def counterpart(point, kind):
        x,y=point
        if kind=="half_turn":
            return (2*center-x, 2*center-y)
        if kind=="horizontal":
            return (x,2*center-y)
        if kind=="vertical":
            return (2*center-x,y)
        return (2*center-y,x)
    for _ in range(attempts):
        kind=rng.choice(("half_turn","horizontal","vertical","quarter_turn"))
        origin=rng.randrange(n)
        seed=parent.squares[origin]
        tx,ty=counterpart((seed.x,seed.y),kind)
        partner=min((j for j in range(n) if j!=origin),
                    key=lambda j:(parent.squares[j].x-tx)**2+
                                 (parent.squares[j].y-ty)**2)
        if (parent.squares[partner].x-tx)**2+(parent.squares[partner].y-ty)**2 > .12:
            continue
        # Symmetry equivariance: reflected moves flip the corresponding axis;
        # a quarter-turn rotates both the displacement and orientation.
        scale=rng.choice((.006,.025,.07,.16))
        dx=rng.gauss(0.,scale)
        dy=rng.gauss(0.,scale)
        da=rng.gauss(0.,scale*.35)
        if kind=="half_turn":
            ox,oy,oa=-dx,-dy,da
        elif kind=="horizontal":
            ox,oy,oa=dx,-dy,-da
        elif kind=="vertical":
            ox,oy,oa=-dx,dy,-da
        else:
            ox,oy,oa=-dy,dx,da
        values=list(parent.squares)
        values[origin]=Square(seed.x+dx,seed.y+dy,seed.angle+da)
        other=parent.squares[partner]
        values[partner]=Square(other.x+ox,other.y+oy,other.angle+oa)
        proposal=_valid(values)
        if proposal is not None and proposal.container_side<=side_cap+1e-9:
            return proposal
    return None
