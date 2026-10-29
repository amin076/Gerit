"""Domain-specific visual output for the N-square packing adapter.

Rendering never participates in evaluation, mutation or parent selection.
"""
from pathlib import Path
import json
import math
import shutil
import subprocess

from PIL import Image, ImageDraw

from gerit.geometry import square_vertices, validate_packing

COLORS = ("#82b4dd","#85c7a1","#f1b96d","#b79cde","#dc8d9f",
          "#a0bb68","#77c9cf","#cab69b","#dfa575","#a7acd8",
          "#85cfb0","#d4a18f")


def render_packing(path, packing, *, generation, initial_side, parents, evaluations,
                   size=900):
    """Draw a valid unit-square configuration at a fixed camera scale."""
    if not validate_packing(packing,tolerance=0.).valid:
        raise ValueError("Refusing to render invalid packing")
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    im=Image.new("RGB",(size,size),"#ffffff")
    draw=ImageDraw.Draw(im)
    left=65
    top=106
    extent=size-145
    scale=extent/(initial_side+0.2)
    def xy(x,y):
        return (round(left+x*scale),round(top+(initial_side-y)*scale))
    L=packing.container_side
    draw.rectangle((*xy(0,L),*xy(L,0)),outline="#27364a",width=4)
    for i,s in enumerate(packing.squares):
        vertices=[xy(x,y) for x,y in square_vertices(s)]
        draw.polygon(vertices,fill=COLORS[i%len(COLORS)])
        draw.line(vertices+[vertices[0]],fill="#263445",width=2)
        center=xy(s.x,s.y)
        draw.text((center[0]-5,center[1]-6),str(i+1),fill="#263445")
    draw.text((left,25),f"Gerit {len(packing.squares)} squares | generation {generation} | parents {parents}",fill="#172332")
    draw.text((left,48),f"L={L:.12f}",fill="#172332")
    draw.text((left,71),f"Evaluations={evaluations}",fill="#556476")
    im.save(path)


class PackingRecorder:
    def __init__(self, output, initial_side, *, video=False, fps=30, width=900,
                 frame_every=1):
        if fps<1 or width<320 or frame_every<1:
            raise ValueError("fps>=1, image-width>=320, frame-every>=1 are required")
        if video and shutil.which("ffmpeg") is None:
            raise RuntimeError("Video requested but ffmpeg not on PATH; install ffmpeg or omit --video")
        self.output=Path(output)
        self.initial_side=initial_side
        self.video=video
        self.fps=fps
        self.width=width
        self.frame_every=frame_every
        self.frames=self.output/"frames"
        self.frame_count=0
        self.last_generation=None
        self.last_packing=None
        self.last_parents=1
        self.last_evaluations=0
        self.output.mkdir(parents=True,exist_ok=True)
        if video:
            self.frames.mkdir(parents=True,exist_ok=True)

    def __call__(self,generation,state,objective,parents,evaluations):
        self.last_generation=generation
        self.last_packing=state
        self.last_parents=parents
        self.last_evaluations=evaluations
        # Final/latest image is replaced atomically per generation.
        target=self.output/"latest_packing.png"
        temporary=self.output/"latest_packing.tmp.png"
        render_packing(temporary,state,generation=generation,initial_side=self.initial_side,
                       parents=parents,evaluations=evaluations,size=self.width)
        temporary.replace(target)
        if self.video and generation>0 and generation%self.frame_every==0:
            self.frame_count+=1
            render_packing(self.frames/f"frame_{self.frame_count:06d}.png",state,
                 generation=generation,initial_side=self.initial_side,
                 parents=parents,evaluations=evaluations,size=self.width)

    def finish(self):
        if self.last_packing is None:
            return
        render_packing(self.output/"final_packing.png",self.last_packing,
                       generation=self.last_generation,initial_side=self.initial_side,
                       parents=self.last_parents,evaluations=self.last_evaluations,
                       size=self.width)
        if not self.video or not self.frame_count:
            return
        cmd=["ffmpeg","-hide_banner","-loglevel","error","-y","-framerate",
             str(self.fps),"-start_number","1","-i",
             str(self.frames/"frame_%06d.png"),"-frames:v",str(self.frame_count),
             "-c:v","libx264","-pix_fmt","yuv420p","-crf","20",
             str(self.output/"packing.mp4")]
        subprocess.run(cmd,check=True)
        print(f"VIDEO {self.output/'packing.mp4'} frames={self.frame_count} fps={self.fps}",flush=True)


def render_best_ancestry_video(output, problem, *, fps=30, width=900,
                               camera_side=6.0):
    """Follow exact parent-state IDs from the final best state back to this run's root.

    This is NOT a global-best-over-time video. A warm start is the root of
    the current run; genealogy from earlier runs cannot be inferred.
    """
    output=Path(output)
    best=json.loads((output/"best.json").read_text(encoding="utf8"))
    target=best.get("best_node_id")
    if target is None:
        raise ValueError("This run has no node IDs; run with the genealogy-enabled engine")
    nodes={}
    with (output/"genealogy.jsonl").open(encoding="utf8") as file:
        for line in file:
            row=json.loads(line)
            nodes[row["node_id"]]=row
    chain=[]
    visited=set()
    current=target
    while current is not None:
        if current in visited:
            raise ValueError("Cycle in ancestry")
        visited.add(current)
        if current not in nodes:
            raise ValueError(f"Missing ancestor node {current}; ancestry is incomplete")
        node=nodes[current]
        chain.append(node)
        current=node["parent_node_id"]
    chain.reverse()
    if not chain or chain[0]["parent_node_id"] is not None:
        raise ValueError("Ancestry does not reach the initial root")
    if not chain[-1]["state"] == best["state"]:
        raise ValueError("Final ancestry state differs from best.json")
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg must be on PATH to encode ancestry video")

    frames=output/"best_ancestry_frames"
    frames.mkdir(parents=True,exist_ok=True)
    for index,node in enumerate(chain,1):
        packing=problem.decode(node["state"])
        render_packing(frames/f"frame_{index:06d}.png",packing,
                       generation=node["generation"],initial_side=camera_side,
                       parents=1,evaluations=node["evaluation"],size=width)
    video=output/"best_ancestry.mp4"
    cmd=["ffmpeg","-hide_banner","-loglevel","error","-y",
         "-framerate",str(fps),"-start_number","1","-i",
         str(frames/"frame_%06d.png"),"-frames:v",str(len(chain)),
         "-c:v","libx264","-pix_fmt","yuv420p","-crf","20",str(video)]
    subprocess.run(cmd,check=True)
    manifest={"best_node_id":target,"root_node_id":chain[0]["node_id"],
              "node_count":len(chain),"fps":fps,
              "source":"exact_parent_node_links","warm_start_boundary":True,
              "nodes":[{"node_id":row["node_id"],
                        "parent_node_id":row["parent_node_id"],
                        "generation":row["generation"],
                        "evaluation":row["evaluation"]}
                       for row in chain]}
    (output/"best_ancestry.json").write_text(
        json.dumps(manifest,indent=2),encoding="utf8")
    print(f"ANCESTRY_VIDEO {video} nodes={len(chain)} fps={fps}",flush=True)
    return video
