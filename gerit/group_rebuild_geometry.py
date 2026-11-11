"""Break a local cluster, rebuild it with one extra rotated square.

Unlike fixed-gap insertion this operator removes a group of k existing
squares from a good N-square packing and searches for k+1 placements.
The other N-k squares remain fixed. It retains legal rotated candidates,
including solutions temporarily worse than the winner within the target
side cap. This is a heuristic operator, not a proof of optimality.
"""
from __future__ import annotations

import math
import random

from .geometry import Packing, Square, minimum_bounding_square, squares_overlap, validate_packing

ANGLES=(0.0, math.pi/12, math.pi/6, math.pi/4, -math.pi/12, -math.pi/6, -math.pi/4)


def _overlaps(sq: Square, existing: list[Square]) -> bool:
    return any(abs(sq.x-other.x)<1.42 and abs(sq.y-other.y)<1.42
               and squares_overlap(sq,other,tolerance=0.0)
               for other in existing)


def _sites(placed: list[Square], removed: list[Square], limit:float,
           rng:random.Random, random_probes:int):
    """Candidate poses near released vacancies, neighboring contacts and walls."""
    delta=4e-5
    sites=[]
    for s in removed:
        sites.extend([(s.x,s.y),(s.x+delta,s.y+delta),
                      (s.x-delta,s.y-delta)])
        for dx,dy in ((.15,0),(-.15,0),(0,.15),(0,-.15),
                      (.4,.4),(-.4,.4),(.4,-.4),(-.4,-.4)):
            sites.append((s.x+dx,s.y+dy))
    # local contact-derived sites; sampling prevents O(N²) in large packings.
    anchors=(rng.sample(placed,min(50,len(placed))) if placed else [])
    for s in anchors:
        for dx,dy in ((1+delta,0),(-1-delta,0),(0,1+delta),(0,-1-delta),
                      (1+delta,1+delta),(-1-delta,1+delta),
                      (1+delta,-1-delta),(-1-delta,-1-delta)):
            sites.append((s.x+dx,s.y+dy))
    # Random placement sites across the whole target envelope.
    for _ in range(random_probes):
        sites.append((rng.uniform(.51,max(.52,limit-.51)),
                      rng.uniform(.51,max(.52,limit-.51))))
    rng.shuffle(sites)
    return sites


def _build_candidate(remaining:list[Square],removed:list[Square],limit:float,
                     rng:random.Random,probes:int):
    placed=list(remaining)
    for index in range(len(removed)+1):
        candidates=[]
        for x,y in _sites(placed,removed,limit,rng,probes):
            for angle in rng.sample(ANGLES,len(ANGLES)):
                radius=.5*(abs(math.sin(angle))+abs(math.cos(angle)))
                if x-radius<2e-5 or y-radius<2e-5 or x+radius>limit-2e-5 or y+radius>limit-2e-5:
                    continue
                sq=Square(x,y,angle)
                if _overlaps(sq,placed):
                    continue
                # Sampling promotes geometric variety, not merely grid filling.
                candidates.append(sq)
                if len(candidates)>=12:
                    break
            if len(candidates)>=12:
                break
        if not candidates:
            return None
        # Most trials are greedily compact; some take alternative void poses.
        def measure(s):
            return max(max((p.x for p in placed),default=0.),s.x,
                       max((p.y for p in placed),default=0.),s.y)
        placed.append(min(candidates,key=measure) if rng.random()<.65
                      else rng.choice(candidates))
    packing=minimum_bounding_square(placed)
    if packing.container_side>=limit-1e-9:
        return None
    if not validate_packing(packing,tolerance=0.0).valid:
        return None
    return packing


def rebuild_with_extra(source:Packing, target_cap:float, *,
                       seed:int, attempts:int=100, group_size:int=3,
                       probes:int=75):
    """Return best feasible N+1 pose and search counters.

    A local neighborhood of group_size squares is deleted, then group_size
    plus one squares are reintroduced with free positions and rotations.
    Every proposed final configuration is strictly validated.
    """
    if attempts<1 or probes<1 or group_size<1:
        raise ValueError("Positive search budgets required")
    if not math.isfinite(target_cap) or target_cap<=0:
        raise ValueError("target cap must be positive")
    base=minimum_bounding_square(source.squares)
    n=len(base.squares)
    if n<group_size:
        raise ValueError("group size cannot exceed source count")
    rng=random.Random(seed)
    best=None
    verified=0
    for attempt in range(attempts):
        pivot=rng.randrange(n)
        center=base.squares[pivot]
        # With probability 1/4 use a far-off square: historical-like
        # large relocation rather than always a tight local neighborhood.
        if rng.random()<.25:
            removed_ids=set(rng.sample(range(n),group_size))
        else:
            nearest=sorted(range(n),key=lambda i:
                (base.squares[i].x-center.x)**2+(base.squares[i].y-center.y)**2)
            removed_ids=set(nearest[:group_size])
        removed=[s for i,s in enumerate(base.squares) if i in removed_ids]
        remaining=[s for i,s in enumerate(base.squares) if i not in removed_ids]
        candidate=_build_candidate(remaining,removed,
                                  min(target_cap,best.container_side if best else target_cap),
                                  rng,probes)
        if candidate is None:
            continue
        verified+=1
        if best is None or candidate.container_side<best.container_side-1e-10:
            best=candidate
    return best,{"attempts":attempts,"strict_valid":verified,
                 "group_size":group_size,"probes":probes}
