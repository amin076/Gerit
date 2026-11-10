"""Contact-aware, geometry-only compaction for unit-square packings.

This module modifies candidate poses only. It has no parent selection,
generation scheduler, learned policy, or special five-square solution.
It searches joint translational/rotational perturbations near the current
contact graph and preserves only strictly valid, non-worsening results.
"""
from __future__ import annotations

import math
import random
from .geometry import Packing, Square, minimum_bounding_square, validate_packing, square_vertices


def _box(p: Packing) -> tuple[float, float, float, float]:
    vertices=(point for sq in p.squares for point in square_vertices(sq))
    xs=[]; ys=[]
    for x,y in vertices:
        xs.append(x);ys.append(y)
    return min(xs),max(xs),min(ys),max(ys)


def _contact_pairs(p: Packing) -> list[tuple[int,int,float]]:
    """Rank proximity via circumscribed vertex-to-segment Euclidean distances.

    This proximity is a *heuristic* for choosing which squares to perturb.
    Final eligibility is determined by the existing exact-tolerance SAT check.
    """
    verts=[square_vertices(s) for s in p.squares]
    def point_segment_dist(px,py,a,b):
        vx=b[0]-a[0];vy=b[1]-a[1]
        t=max(0.,min(1.,((px-a[0])*vx+(py-a[1])*vy)/(vx*vx+vy*vy)))
        return math.hypot(px-a[0]-t*vx,py-a[1]-t*vy)
    out=[]
    for i in range(len(verts)):
        for j in range(i+1,len(verts)):
            a,b=verts[i],verts[j]
            d=min(point_segment_dist(x,y,b[k],b[(k+1)%4])
                  for x,y in a for k in range(4))
            d=min(d,min(point_segment_dist(x,y,a[k],a[(k+1)%4])
                        for x,y in b for k in range(4)))
            out.append((i,j,d))
    out.sort(key=lambda item:item[2])
    return out


def propose_contact_compaction(parent: Packing, rng: random.Random,
                               side_cap: float, *, attempts: int = 120,
                               scales: tuple[float,float,float] = (0.040, 0.013, 0.003)
                               ) -> Packing | None:
    """Locally optimize a *valid* packing using joint contact-adjacent moves.

    Trials search multiple scales. Every square may rotate and translate.
    Moves include tight-boundary nudges, nearest-contact pair adjustments,
    and joint up-to-all-square moves. A feasible better pose is retained
    even when intermediate proposals are invalid; invalid proposals are
    never parents. No precomputed solution geometry is used.
    """
    if (len(scales)!=3 or any(not math.isfinite(v) or v<=0 for v in scales)
            or not (scales[0]>=scales[1]>=scales[2])):
        raise ValueError('scales must be three finite, positive, nonincreasing numbers')
    if not math.isfinite(side_cap) or attempts<1 or side_cap<1:
        return None
    if not validate_packing(parent,tolerance=0.0).valid:
        raise ValueError("Contact compaction needs valid initial packing")
    best=minimum_bounding_square(parent.squares)
    if not validate_packing(best,tolerance=0.0).valid:
        best=parent
    if best.container_side>side_cap+1e-9:
        return None
    current=best
    accepted=0
    n=len(best.squares)
    if n<2:
        return best
    for trial in range(attempts):
        fraction=trial/max(1,attempts-1)
        scale=(scales[0] if fraction<.30 else scales[1] if fraction<.65 else scales[2])
        angle_scale=scale*.72
        squares=list(current.squares)
        x0,x1,y0,y1=_box(current)
        center_x=(x0+x1)*.5;center_y=(y0+y1)*.5
        pairs=_contact_pairs(current)
        roll=rng.random()
        if roll<.32 and pairs:
            # Choose a near-contact pair, relax both centers, rotate freely.
            limit=max(1,min(len(pairs),n))
            i,j,_=pairs[rng.randrange(limit)]
            indices=(i,j)
        elif roll<.78:
            # Boundary-active square and its nearest neighbor.
            gaps=[]
            for i,s in enumerate(squares):
                corners=square_vertices(s)
                gap=min(min(x-x0 for x,y in corners),
                        min(x1-x for x,y in corners),
                        min(y-y0 for x,y in corners),
                        min(y1-y for x,y in corners))
                gaps.append(1/(.002+max(0,gap)))
            i=rng.choices(range(n),weights=gaps,k=1)[0]
            neighbors=sorted((j for j in range(n) if j!=i),
                             key=lambda j:(squares[i].x-squares[j].x)**2+
                                          (squares[i].y-squares[j].y)**2)
            indices=(i,neighbors[0]) if rng.random()<.65 else (i,)
        else:
            # Occasionally let the whole nearby structure shift/rotate.
            indices=tuple(rng.sample(range(n),rng.randint(2,n)))
        dx=rng.gauss(0,scale)
        dy=rng.gauss(0,scale)
        da=rng.gauss(0,angle_scale)
        values=list(squares)
        for i in indices:
            s=squares[i]
            # Weak shrink-to-centroid bias, but freely reversible noise.
            nx=s.x+dx*.40+rng.gauss(0,scale*.75)+.10*scale*(center_x-s.x)
            ny=s.y+dy*.40+rng.gauss(0,scale*.75)+.10*scale*(center_y-s.y)
            angle=s.angle+da*.45+rng.gauss(0,angle_scale*.7)
            values[i]=Square(nx,ny,angle)
        candidate=minimum_bounding_square(tuple(values))
        if candidate.container_side>min(side_cap,current.container_side)+1e-10:
            continue
        if not validate_packing(candidate,tolerance=0.0).valid:
            continue
        if candidate.container_side<current.container_side-1e-11:
            current=candidate
            accepted+=1
        elif abs(candidate.container_side-current.container_side)<1e-11:
            # Neutral move occasionally preserves access to different contacts.
            if rng.random()<.08:
                current=candidate
        if current.container_side<best.container_side-1e-11:
            best=current
    return best if accepted or best.container_side<parent.container_side-1e-11 else None
