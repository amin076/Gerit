"""Experimental N=401..404 square-packings with 1..4 edge/corner diamonds.
This is an isolated, non-registry-mutating structural experiment.
Writes certified numerical seeds, PNG diagrams and summary JSON.
"""
from __future__ import annotations
import argparse
import json
import math
import sys
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from gerit.kaggle import Candidate, validate as independent_validate

SIDE=21.0
HALF=math.sqrt(2)/2
STEP=HALF+0.001
POSITIONS={
 "center":(10.5,10.5,1,1),
 "right_middle":(20.20,10.5,-1,1),
 "right_upper":(20.20,20.20,-1,-1),
 "right_lower":(20.20,0.80,-1,1),
 "top_middle":(10.5,20.20,1,-1),
 "top_left":(0.80,20.20,1,-1),
}
OFFSETS=((0,0),(1,0),(0,1),(1,1))

def diamond_centers(name,d):
 x,y,dx,dy=POSITIONS[name]
 return np.array([[x+i*STEP*dx,y+i*STEP*dy,math.pi/4] for i in range(d)])

def collisions(p):
 """Vectorized exact-shape separating-axis check, with 1e-9 tolerance."""
 pairs=cKDTree(p[:,:2]).query_pairs(1.5,output_type="ndarray")
 if not len(pairs):return np.empty((0,2),dtype=int)
 i,j=pairs.T
 c=np.cos(p[:,2]);s=np.sin(p[:,2]);d=p[j,:2]-p[i,:2]
 axes=np.stack((np.stack((c[i],s[i]),axis=1),
                np.stack((-s[i],c[i]),axis=1),
                np.stack((c[j],s[j]),axis=1),
                np.stack((-s[j],c[j]),axis=1)),axis=1)
 proj=np.einsum("nd,nkd->nk",d,axes)
 diff=p[j,2]-p[i,2]
 support=.5+.5*(np.abs(np.cos(diff))+np.abs(np.sin(diff)))
 margin=np.max(np.abs(proj)-support[:,None],axis=1)
 return pairs[margin < -1e-9]

def contained(p,side=SIDE):
 h=.5*(np.abs(np.cos(p[:,2]))+np.abs(np.sin(p[:,2])))
 return bool(np.all(p[:,:2]-h[:,None]>=-1e-9) and
             np.all(p[:,:2]+h[:,None]<=side+1e-9))

def seed(name,d,offset):
 """Free a slot by relocating every conflicting existing unit square.
 The new rotated squares are edge-adjacent (with 0.001 clearance).
 All 400 original squares remain present: N=400+d.
 """
 ox,oy=offset
 diamond=diamond_centers(name,d)
 grid=np.array([[x+.5+ox,y+.5+oy,0.] for y in range(20)
                for x in range(20)],dtype=float)
 conflict=np.zeros(400,dtype=bool)
 for q in diamond:
  pairs=collisions(np.vstack((grid,q[None,:])))
  conflict[pairs[pairs[:,1]==400,0]]=True
 remaining=grid[~conflict]
 missing=int(np.count_nonzero(conflict))
 occupied={(round(x,5),round(y,5)) for x,y,_ in remaining}
 available=[]
 for y in range(21):
  for x in range(21):
   cell=np.array([x+.5,y+.5,0.])
   if (round(cell[0],5),round(cell[1],5)) in occupied:continue
   if len(collisions(np.vstack((diamond,cell[None,:]))))==0:
    available.append(cell)
 # Relocate blocked squares away from the diamond; this makes a large
 # empty patch near the rotated cluster without freezing original tiles.
 cx,cy=diamond[0,:2]
 available.sort(key=lambda t:(-((t[0]-cx)**2+(t[1]-cy)**2),t[1],t[0]))
 if len(available)<missing:return None
 replacements=np.array(available[:missing],dtype=float).reshape(missing,3)
 p=np.vstack((remaining,replacements,diamond))
 if len(p)!=400+d or not contained(p) or len(collisions(p)):return None
 h=.5*(np.abs(np.cos(p[:,2]))+np.abs(np.sin(p[:,2])))
 left=np.min(p[:,0]-h);right=np.max(p[:,0]+h)
 bottom=np.min(p[:,1]-h);top=np.max(p[:,1]+h)
 side=float(max(right-left,top-bottom))
 p[:,:2]-=[left,bottom]
 return p,missing,side

def make_figure(p,path,title,d):
 import matplotlib
 matplotlib.use("Agg")
 import matplotlib.pyplot as plt
 from matplotlib.patches import Rectangle,Polygon
 from matplotlib.collections import PatchCollection
 f,ax=plt.subplots(figsize=(6.5,6.5))
 tiles=[Rectangle((x-.5,y-.5),1,1) for x,y,_ in p[:-d]]
 ax.add_collection(PatchCollection(tiles,facecolor="#b5dafa",
                                  edgecolor="#325a82",linewidth=.24))
 corners=np.array([[-.5,-.5],[.5,-.5],[.5,.5],[-.5,.5]])
 for x,y,a in p[-d:]:
  rot=np.array([[math.cos(a),-math.sin(a)],[math.sin(a),math.cos(a)]])
  ax.add_patch(Polygon(corners@rot.T+[x,y],facecolor="#fa9276",
                       edgecolor="#8d3426",linewidth=1))
 ax.plot([0,SIDE,SIDE,0,0],[0,0,SIDE,SIDE,0],color="black",lw=1.4)
 ax.set(xlim=(-.2,SIDE+.2),ylim=(-.2,SIDE+.2),title=title,
        xlabel="x",ylabel="y")
 ax.set_aspect("equal")
 f.savefig(path,dpi=135,bbox_inches="tight");plt.close(f)

def run(output_dir,registry=None,max_d=4):
 output=Path(output_dir)
 if output.exists():raise FileExistsError("Preserve existing results: "+str(output))
 output.mkdir(parents=True)
 previous={}
 if registry and Path(registry).is_file():
  b=json.loads(Path(registry).read_text(encoding="utf-8"))
  previous={n:float(b["problems"][str(n)]["side"]) for n in range(401,405)}
 if not previous:
  from gerit.four_corner_center_45 import four_corner_center_45
  previous={n:21.0 for n in range(401,405)}
  previous[401]=four_corner_center_45(401).container_side
 rows=[]
 for d in range(1,max_d+1):
  n=400+d
  for name in POSITIONS:
   choices=[]
   for offset in OFFSETS:
    candidate=seed(name,d,offset)
    if candidate is not None:choices.append((*candidate,offset))
   row=dict(n=n,diamonds=d,position=name,valid=False,
            incumbent_side=previous.get(n),trials=len(OFFSETS))
   if choices:
    p,moved,side,offset=min(choices,key=lambda item:(item[2],item[1]))
    verdict=independent_validate(Candidate(n,
      tuple((repr(x),repr(y),repr(a)) for x,y,a in p),
      "boundary_diamond_study",side))
    row.update(valid=bool(verdict.valid),validator=verdict.reason,
               side=side,relocated_squares=moved,offset=list(offset),
               improved=bool(verdict.valid and side<previous[n]-1e-10))
    if verdict.valid:
     filename=f"n{n}_{name}"
     (output/(filename+".json")).write_text(json.dumps(dict(
       n=n,side=side,
       squares=[dict(x=float(x),y=float(y),angle=float(a)) for x,y,a in p],
       experiment="boundary_diamond_study",registry_updated=False
     ),indent=2)+"\n",encoding="utf-8")
     make_figure(p,output/(filename+".png"),
                 f"N={n}, diamonds={d}, {name}, L={side:.6f}",d)
   rows.append(row)
   print(f"CASE N={n} {name} valid={row['valid']} "
         f"L={row.get('side')} reason={row.get('validator')} improved={row.get('improved',False)}",flush=True)
 summary=dict(method="boundary_diamond_discrete_relocation",
              experimental=True,registry_modified=False,
              valid=sum(r["valid"] for r in rows),
              improved=sum(r.get("improved",False) for r in rows),
              results=rows)
 (output/"summary.json").write_text(json.dumps(summary,indent=2)+"\n",
                                    encoding="utf-8")
 print(f"FINISHED valid={summary['valid']} improved={summary['improved']}",
       flush=True)
 return summary

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("--output-dir",default="results/gerit_boundary_diamonds_401")
 p.add_argument("--registry",default="results/kaggle_baseline/best_registry.json")
 p.add_argument("--max-d",type=int,default=4)
 a=p.parse_args()
 if not 1<=a.max_d<=4:p.error("--max-d should be 1..4")
 run(a.output_dir,a.registry,a.max_d)

if __name__=="__main__":main()
