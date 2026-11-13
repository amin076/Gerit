"""Generate REAL N=901 unit-square packing morphs with constant enclosing side.

For any integer 1 <= a,b <= 29, split a 30x30 grid into four
rectangles with dimensions:
  bottom left  a x b;         bottom right  (30-a) x b
  top left     a x (30-b);    top right     (30-a) x (30-b)
and insert one 45-degree UNIT square at the cross intersection.
The clear cross has width g=1/sqrt(2)+clearance, so L=30+g.
This construction remains overlap-free for all 1<=a,b<=29.

Path: (a,b)=(15,15) -> (29,15) -> (29,29).
The tempting endpoints a=30 or b=30 are NOT certified by this
four-block family: the diamond would extend beyond the container.
All 900 axis-aligned squares stay exactly unit-size; no display scaling.

Outputs: one PNG and coordinates JSON per certified frame, one contact
sheet, and a detailed manifest. No registry or competition files touched.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gerit.geometry import Square, Packing, square_vertices, square_inside_container, squares_overlap
from gerit.kaggle import Candidate, validate as interval_validate

COUNT=30
DIAMOND_ANGLE=math.pi/4


@dataclass(frozen=True)
class MorphFrame:
    a:int
    b:int
    packing:Packing
    group_sizes:dict[str,tuple[int,int]]
    stage:str


def build_packing(a:int,b:int,clearance:float=4e-6, stage:str=""):
    """Create coordinates for 900 genuinely unit-size cells and one diamond."""
    if type(a) is not int or type(b) is not int or not (1<=a<COUNT and 1<=b<COUNT):
        raise ValueError("This four-block construction requires 1<=a,b<=29")
    if not math.isfinite(clearance) or not 1e-7<=clearance<=.001:
        raise ValueError("clearance must be in [1e-7, .001]")
    gap=math.sqrt(.5)+clearance
    side=COUNT+gap
    left, right=a,COUNT-a
    bottom, top=b,COUNT-b
    groups={
        "bottom_left":(left,bottom),
        "top_left":(left,top),
        "bottom_right":(right,bottom),
        "top_right":(right,top)
    }
    squares=[]
    for x_start, ncols in ((0,left),(a+gap,right)):
        for y_start, nrows in ((0,bottom),(b+gap,top)):
            for ix in range(ncols):
                for iy in range(nrows):
                    squares.append(Square(float(x_start+ix+.5),
                                          float(y_start+iy+.5),0.))
    squares.append(Square(a+gap/2,b+gap/2,DIAMOND_ANGLE))
    packing=Packing(tuple(squares),side)
    assert len(packing.squares)==901
    assert sum(w*h for w,h in groups.values())==900
    return MorphFrame(a,b,packing,groups,stage)


def quick_validate(frame:MorphFrame):
    """Independent analytic grid guarantee + numerical SAT at moving diamond."""
    p=frame.packing
    diamonds=p.squares[-1:]
    others=p.squares[:-1]
    assert len(others)==900 and len(diamonds)==1
    if not all(square_inside_container(s,p.container_side,tolerance=1e-9) for s in p.squares):
        return False,"square outside container"
    diamond=diamonds[0]
    near=0
    for s in others:
        if abs(s.x-diamond.x)>1.5 or abs(s.y-diamond.y)>1.5:
            continue
        near+=1
        if squares_overlap(s,diamond,tolerance=1e-11):
            return False,f"overlap with square ({s.x},{s.y})"
    # Distinct integer-lattice cells in each of four disjoint rectangles.
    # This proof avoids O(900^2) brute force.
    xleft={round(s.x-.5,9) for s in others if s.x<frame.a}
    assert len(xleft)==frame.a
    return True,f"local SAT clear ({near} neighbors checked), blocks disjoint"


def interval_certificate(frame:MorphFrame):
    p=frame.packing
    candidate=Candidate(901,tuple((repr(s.x),repr(s.y),repr(s.angle))
                               for s in p.squares),
                        "exact_901_cluster_morph",p.container_side)
    proof=interval_validate(candidate)
    return proof.valid,proof.reason,proof.side


def path_frames(clearance:float=4e-6):
    coords=[(a,15) for a in range(15,30)]
    coords += [(29,b) for b in range(16,30)]
    return [build_packing(a,b,clearance,"center_to_right" if i<15 else "right_to_top")
            for i,(a,b) in enumerate(coords)]


def render(frame:MorphFrame,path:Path,index:int,dpi:int):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon,Rectangle
    from matplotlib.collections import PatchCollection

    p=frame.packing
    side=p.container_side
    fig,ax=plt.subplots(figsize=(8,8))
    patches=[Rectangle((s.x-.5,s.y-.5),1,1) for s in p.squares[:-1]]
    ax.add_collection(PatchCollection(patches,facecolor="#bcdafa",
                          edgecolor="#386b9e",linewidth=.20))
    diamond=p.squares[-1]
    ax.add_patch(Polygon(square_vertices(diamond),closed=True,
                         facecolor="#f2a65a",edgecolor="#95431b",
                         linewidth=1.7,zorder=4))
    ax.add_patch(Rectangle((0,0),side,side,fill=False,
                           edgecolor="#17202e",linewidth=1.5,zorder=5))
    ax.set_aspect("equal")
    ax.set_xlim(-.3,side+.3);ax.set_ylim(-.3,side+.3)
    ax.set_title(f"N=901   frame {index:02d}   a={frame.a}  b={frame.b}\n"
                 f"REAL unit squares, no overlap   L={side:.12f}",fontsize=11)
    ax.set_xlabel("x");ax.set_ylabel("y")
    fig.tight_layout()
    fig.savefig(path,dpi=dpi)
    plt.close(fig)


def render_sheet(images:list[Path],destination:Path,cols:int):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows=math.ceil(len(images)/cols)
    fig,axes=plt.subplots(rows,cols,figsize=(3.5*cols,3.55*rows))
    flat=list(axes.flat) if hasattr(axes,"flat") else [axes]
    for ax,path in zip(flat,images):
        ax.imshow(plt.imread(path));ax.set_title(path.stem,fontsize=8);ax.axis("off")
    for ax in flat[len(images):]:ax.axis("off")
    fig.tight_layout();fig.savefig(destination,dpi=110);plt.close(fig)


def run(output:Path,clearance:float=4e-6,dpi:int=130,columns:int=4,
        certify_all:bool=True):
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("Existing results protected; choose a new output dir: "+str(output))
    (output/"frames").mkdir(parents=True,exist_ok=True)
    (output/"coordinates").mkdir(parents=True,exist_ok=True)
    frames=path_frames(clearance)
    records=[];images=[]
    for i,f in enumerate(frames):
        valid,reason=quick_validate(f)
        if not valid:raise RuntimeError(f"Frame {i} INVALID: {reason}")
        if certify_all:
            certified,proof_reason,cert_side=interval_certificate(f)
            if not certified:raise RuntimeError(f"Frame {i} interval SAT FAILED: {proof_reason}")
        else:
            certified=None;proof_reason="not run";cert_side=None
        img=output/"frames"/f"frame_{i:02d}.png"
        coords=output/"coordinates"/f"frame_{i:02d}.json"
        render(f,img,i,dpi);images.append(img)
        coords.write_text(json.dumps(dict(n=901,side=f.packing.container_side,
            a=f.a,b=f.b,stage=f.stage,
            squares=[dict(x=s.x,y=s.y,angle=s.angle)
                     for s in f.packing.squares]),indent=2)+"\n",encoding="utf-8")
        row=dict(index=i,a=f.a,b=f.b,stage=f.stage,
                 groups={k:list(v) for k,v in f.group_sizes.items()},
                 fixed_side=f.packing.container_side,
                 n=901,axis_aligned=900,rotated=1,unit_side=1.,
                 valid=valid,certified_interval_sat=certified,
                 validator_reason=proof_reason,certified_side=cert_side,
                 image=str(img),coordinates=str(coords))
        records.append(row)
        print(f"FRAME {i+1:02d}/{len(frames)} a={f.a:02d} b={f.b:02d} "
              f"VALID L={f.packing.container_side:.12f} interval={certified}",
              flush=True)
    render_sheet(images,output/"contact_sheet.png",columns)
    manifest=dict(n=901,side=frames[0].packing.container_side,
                  exact_unit_squares=True,no_display_scaling=True,
                  all_frames_valid=True,frames=records,
                  endpoint_warning=("At a=30 or b=30 the four-rectangle method "
                     "cannot fit the diamond in the same container; last valid "
                     "frames reach (29,15) and (29,29), not the actual edge."))
    (output/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    print(f"FINISHED VALID_FRAMES={len(frames)} "
          f"L={frames[0].packing.container_side:.12f} "
          f"OUTPUT={output}",flush=True)
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir",type=Path,default=Path("results/cluster_morph_901_exact"))
    p.add_argument("--clearance",type=float,default=4e-6)
    p.add_argument("--dpi",type=int,default=130)
    p.add_argument("--columns",type=int,default=4)
    p.add_argument("--skip-interval-certification",action="store_true")
    args=p.parse_args()
    if args.dpi<50 or args.columns<1:p.error("dpi>=50 and columns>=1 required")
    run(args.output_dir,args.clearance,args.dpi,args.columns,
        not args.skip_interval_certification)


if __name__=="__main__":
    main()
