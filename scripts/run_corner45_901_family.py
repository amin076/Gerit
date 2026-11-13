"""N=901 fixed-side vacancy-gathering trial, upper-right 45 degree square.

Independent experimental workflow: NEVER touches the best-answer registry.
1. Prove the existing N901 center-45 founder using independent interval SAT.
2. Build an off-center/upper-right rotated-square founder with a 31x31 envelope.
   Move every displaced grid tile into a different free lattice cell.
3. Extend the construction to N902..905 by occupying additional free cells.
4. Numerically relax ALL centers and ALL angles into the SAME N901 side cap
   with a soft corner anchor. Count only fully certified final results.
5. Save before/after PNG, valid JSON founders, diagnostics and summary.
A failed numerical search does NOT prove a fixed-side packing impossible.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import sys
import numpy as np
from scipy.optimize import minimize
from scipy.spatial import cKDTree
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from gerit.four_corner_center_45 import four_corner_center_45
from gerit.kaggle import Candidate,validate as interval_validate
from gerit.elastic_growth import ElasticEnergy
from gerit.elastic_repair import feasibility_diagnostics

DIAMOND=math.pi/4
HALF=math.sqrt(.5)
GRID=30
ENVELOPE=31.
TARGETS=(901,902,903,904,905)

def overlap_pairs(p):
 p=np.asarray(p,float)
 near=cKDTree(p[:,:2]).query_pairs(1.5,output_type="ndarray")
 if not len(near):return near
 i,j=near.T
 c=np.cos(p[:,2]);s=np.sin(p[:,2])
 axes=np.stack((np.column_stack((c[i],s[i])),
                np.column_stack((-s[i],c[i])),
                np.column_stack((c[j],s[j])),
                np.column_stack((-s[j],c[j]))),axis=1)
 proj=np.einsum("nd,nkd->nk",p[j,:2]-p[i,:2],axes)
 delta=p[j,2]-p[i,2]
 support=.5+.5*(np.abs(np.cos(delta))+np.abs(np.sin(delta)))
 return near[np.max(np.abs(proj)-support[:,None],axis=1)<-1e-8]

def corner_founder(n, *, edge=ENVELOPE, corner="upper_right"):
 """All 900 grid tiles are preserved; collided tiles move to empty cells."""
 if not 901<=n<=910:raise ValueError("Only 901..910")
 positions={"upper_right":(edge-HALF-.005,edge-HALF-.005),
            "upper_left":(HALF+.005,edge-HALF-.005)}
 if corner not in positions:raise ValueError(corner)
 xy=positions[corner]
 diamond=np.array([[xy[0],xy[1],DIAMOND]])
 grid=np.array([[x+.5,y+.5,0] for y in range(GRID)
                for x in range(GRID)],dtype=float)
 # A grid tile intersects the 45 degree diamond if their SAT overlaps.
 bad=[]
 for i,p in enumerate(grid):
  if len(overlap_pairs(np.vstack((p,diamond)))):bad.append(i)
 remain=np.delete(grid,bad,axis=0)
 used={(float(x),float(y)) for x,y,_ in remain}
 free=[]
 for y in range(int(edge)):
  for x in range(int(edge)):
   p=np.array([x+.5,y+.5,0.])
   if (p[0],p[1]) in used:continue
   if len(overlap_pairs(np.vstack((p,diamond)))):continue
   free.append(p)
 free.sort(key=lambda p:(-np.sum((p[:2]-diamond[0,:2])**2),
                          float(p[1]),float(p[0])))
 required=len(bad)+(n-901)
 if len(free)<required:raise RuntimeError("No vacant grid cells")
 p=np.vstack((remain,np.asarray(free[:required]).reshape(required,3),diamond))
 assert len(p)==n and len(overlap_pairs(p))==0
 return p,dict(relocated=len(bad),added=n-901,available_after=len(free)-required,
               diamond=list(map(float,diamond[0])),edge=float(edge))

def certify(p,side,source):
 poses=tuple(tuple(repr(float(z)) for z in item) for item in p)
 return interval_validate(Candidate(len(p),poses,source,float(side)))

def records(p,side,name):
 return dict(n=len(p),side=float(side),source=name,
             squares=[dict(x=float(x),y=float(y),angle=float(a)) for x,y,a in p])

def plot(p,side,path,title):
 import matplotlib
 matplotlib.use("Agg")
 import matplotlib.pyplot as plt
 from matplotlib.patches import Polygon
 from matplotlib.collections import PatchCollection
 fig,ax=plt.subplots(figsize=(8,8))
 base=np.array([[-.5,-.5],[.5,-.5],[.5,.5],[-.5,.5]])
 unrot=[];rot=[]
 for x,y,a in p:
  c,s=math.cos(a),math.sin(a)
  v=base@np.array([[c,s],[-s,c]])+np.array([x,y])
  (rot if abs(a)>0.1 else unrot).append(Polygon(v,closed=True))
 if unrot:ax.add_collection(PatchCollection(unrot,facecolor="#c0dafa",
                                            edgecolor="#5278a4",lw=.23))
 if rot:ax.add_collection(PatchCollection(rot,facecolor="#f19b79",
                                         edgecolor="#ac321d",lw=.75))
 ax.plot([0,side,side,0,0],[0,0,side,side,0],color="black",lw=1.2)
 ax.set(xlim=(-.2,side+.2),ylim=(-.2,side+.2),title=title)
 ax.set_aspect("equal")
 fig.savefig(path,dpi=130,bbox_inches="tight");plt.close(fig)

def relax_corner(seed,cap,desired,*,iterations=80):
 """All N squares translate and rotate; diamond remains near top-right.
 Penalty optimization is only an explorer; certification is separate.
 """
 n=len(seed)
 z=np.r_[seed[:,:2].ravel(),seed[:,2]]
 angle_anchor=seed[:,2].copy()
 for weight in (1.,20.,300.):
  E=ElasticEnergy(n,cap,angle_anchor,weight=weight,angle_weight=1e-4)
  def objective(v):
   cost,grad=E(v)
   diff=v[2*n-2:2*n]-desired
   anchor_strength=25*weight
   cost+=anchor_strength*float(diff@diff)
   grad[2*n-2:2*n]+=2*anchor_strength*diff
   return cost,grad
  result=minimize(objective,z,method="L-BFGS-B",jac=True,
    bounds=[(-.5,cap+.5)]*(2*n)+[(-math.pi/4,math.pi/4)]*n,
    options=dict(maxiter=iterations,ftol=1e-11,gtol=1e-6))
  z=result.x
 return np.c_[z[:2*n].reshape(n,2),z[2*n:]]

def run(output,*,max_n=905,iterations=80):
 output=Path(output)
 if output.exists():raise FileExistsError("Existing output is protected: "+str(output))
 output.mkdir(parents=True)
 base=four_corner_center_45(901)
 cap=base.container_side
 center=np.array([(s.x,s.y,s.angle) for s in base.squares])
 baseline=certify(center,cap,"center45_901")
 plot(center,cap,output/"n901_center_certified.png",
      f"N901: certified center-45 founder, L={cap:.9f}")
 rows=[]
 print(f"CENTER_BASELINE valid={baseline.valid} L={cap:.12f} reason={baseline.reason}",flush=True)
 if not baseline.valid:raise ValueError(baseline.reason)
 for n in range(901,max_n+1):
  for position in ("upper_right","upper_left"):
   p,stats=corner_founder(n,corner=position)
   raw=certify(p,ENVELOPE,f"n{n}_corner_{position}_founder")
   if not raw.valid:raise RuntimeError(f"Invalid founder N={n}: {raw.reason}")
   basename=f"n{n}_{position}"
   (output/(basename+"_founder.json")).write_text(
    json.dumps(records(p,ENVELOPE,"corner_vacancy_relocation"),indent=2)+"\n")
   plot(p,ENVELOPE,output/(basename+"_before.png"),
        f"N{n} {position}: relocated {stats['relocated']}, L=31")
   desired=np.array([cap-HALF-.003,cap-HALF-.003]) if position=="upper_right" else np.array([HALF+.003,cap-HALF-.003])
   # Map founder initially into candidate fixed-cap square and optimize.
   q=p.copy()
   q[:,:2]*=cap/ENVELOPE
   q=relax_corner(q,cap,desired,iterations=iterations)
   diagnostic=feasibility_diagnostics(q,cap)
   # Bounding dimension of the final geometry (not proof of feasibility).
   h=.5*(np.abs(np.cos(q[:,2]))+np.abs(np.sin(q[:,2])))
   xmin=np.min(q[:,0]-h);xmax=np.max(q[:,0]+h)
   ymin=np.min(q[:,1]-h);ymax=np.max(q[:,1]+h)
   measured=float(max(xmax-xmin,ymax-ymin))
   corner_error=float(np.linalg.norm(q[-1,:2]-desired))
   # Validate inside a fixed-cap square, separately from extent check.
   inside=bool(np.all(q[:,:2]-h[:,None]>=0) and
               np.all(q[:,:2]+h[:,None]<=cap))
   if inside and len(overlap_pairs(q))==0:
    proof=certify(q,measured,"fixed_side_corner_experiment")
    certified=bool(proof.valid and measured<=cap+1e-8)
    proof_reason=proof.reason
   else:
    certified=False
    proof_reason="failed containment or overlap precheck"
   plot(q,cap,output/(basename+"_after.png"),
        f"N{n} {position}: attempted L={cap:.6f}; certified={certified}")
   if certified:
    (output/(basename+"_certified.json")).write_text(
     json.dumps(records(q,measured,"fixed_side_corner_experiment"),indent=2)+"\n")
   row=dict(n=n,corner=position,base_side=cap,grid_side=ENVELOPE,
            founder_valid=raw.valid,founder_relocated=stats["relocated"],
            tried_side=cap,certified_at_fixed_side=certified,
            proof_reason=proof_reason,measured_span=measured,
            diamond_target_error=corner_error,
            diagnostic=diagnostic)
   rows.append(row)
   print(f"CASE N={n} corner={position} founder_valid={raw.valid} "
         f"fixed_side_valid={certified} overlaps={diagnostic['overlap_pairs']} "
         f"outside={diagnostic['outside_squares']} span={measured:.8f}",flush=True)
 summary=dict(hypothesis="same side as certified N901 center45",
              base_side=cap,base_valid=baseline.valid,
              fixed_side_valid=sum(row["certified_at_fixed_side"] for row in rows),
              cases=len(rows),registry_modified=False,
              conclusion="Numerical trials are not impossibility proofs",results=rows)
 (output/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
 print(f"FINISHED fixed_side_valid={summary['fixed_side_valid']}/{len(rows)} "
       f"L={cap:.12f}",flush=True)
 return summary

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("--output-dir",default="results/corner45_n901_study")
 p.add_argument("--max-n",type=int,default=905)
 p.add_argument("--iterations",type=int,default=80)
 a=p.parse_args()
 if a.max_n<901 or a.max_n>910:p.error("max-n must be 901..910")
 run(a.output_dir,max_n=a.max_n,iterations=a.iterations)

if __name__=="__main__":main()
