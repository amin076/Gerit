"""Domain-specific visual output for the N-square packing adapter.

Rendering never participates in evaluation, mutation or parent selection.
"""
from pathlib import Path
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
    draw.text((left,48),f"L={L:.12f}   area={L*L:.10f}   empty={L*L-len(packing.squares):.10f}",fill="#172332")
    draw.text((left,71),f"Evaluations={evaluations}   fixed camera L={initial_side:.3f}",fill="#556476")
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
