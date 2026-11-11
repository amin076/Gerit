"""Diagnose near-feasible configurations produced by elastic relaxation.

The SAT margin measures the signed penetration on the best separating
axis: positive values indicate overlap. The boundary excess measures
how far the rotated corners extend outside the target square. This is
not an independent certification; it is only a repair diagnostic.
"""
from __future__ import annotations
import math
import numpy as np
from scipy.spatial import cKDTree


def feasibility_diagnostics(poses, side, *, margin=2e-5):
    p=np.asarray(poses,dtype=float)
    if p.ndim!=2 or p.shape[1]!=3 or not math.isfinite(side):
        raise ValueError("Expected finite N x 3 packing and finite side")
    if not np.all(np.isfinite(p)):
        raise ValueError("Nonfinite packing")
    co=np.cos(p[:,2]); si=np.sin(p[:,2])
    half=.5*(np.abs(co)+np.abs(si))
    outside=np.maximum(0.,half+margin-p[:,0])+np.maximum(0.,p[:,0]+half+margin-side)
    outside+=np.maximum(0.,half+margin-p[:,1])+np.maximum(0.,p[:,1]+half+margin-side)
    pairs=cKDTree(p[:,:2]).query_pairs(1.5,output_type="ndarray")
    overlaps=[]
    if len(pairs):
        i,j=pairs.T
        d=p[j,:2]-p[i,:2]
        axes=np.stack((
            np.column_stack((co[i],si[i])),
            np.column_stack((-si[i],co[i])),
            np.column_stack((co[j],si[j])),
            np.column_stack((-si[j],co[j]))),axis=1)
        proj=np.einsum("nd,nkd->nk",d,axes)
        difference=p[j,2]-p[i,2]
        support=.5+.5*(np.abs(np.cos(difference))+np.abs(np.sin(difference)))
        signed=np.max(np.abs(proj)-support[:,None],axis=1)
        for k in np.where(signed<0)[0]:
            overlaps.append((int(i[k]),int(j[k]),float(-signed[k])))
    overlap_depth=max((d for _,_,d in overlaps),default=0.0)
    return {"overlap_pairs":len(overlaps),"max_penetration":overlap_depth,
            "total_penetration":sum(d for _,_,d in overlaps),
            "outside_squares":int(np.count_nonzero(outside>0)),
            "max_outside":float(np.max(outside,initial=0)),
            "boundary_total":float(np.sum(outside)),
            "worst_pairs":sorted(overlaps,key=lambda q:-q[2])[:5]}


def repair_relaxation(poses,side,*,iterations=700,steps=(1e3,1e4,1e5,1e6)):
    """Refine an existing near-feasible pose without inserting new squares."""
    from .elastic_growth import relax_once
    return relax_once(poses,side,iterations=iterations,
                      penalty_schedule=steps,angle_weight=0.)
