"""12 rigid unit squares in the smallest axis-aligned square, using generic Gerit.

Run from the repository's gerit_core_v1 directory:
  py -3 -m examples.square_packing --iterations 10000 --max-parents 10 ...
All domain geometry and mutation logic lives here; engine.py stays generic.
"""
from __future__ import annotations

import argparse
from dataclasses import fields
import math
from pathlib import Path
import sys

# Import the repository's existing geometry from either a source checkout or module run.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gerit.geometry import Packing, Square, minimum_bounding_square, validate_packing
from gerit.selection import packing_distance
from gerit.local_compression import CompressionSettings, compress_valid
from gerit.adaptive_v4 import propose_micro, propose_reconfigure
from gerit.contact_relocation import propose_contact_relocate
from gerit.learning import LearningController, propose_learned
from gerit_core import Search, Settings
from examples.packing_visualization import PackingRecorder
from examples.packing_rotation import rotate_probe, rotation_statistics


class TwelveSquares:
    """Adapter: constraints and objective belong to THIS problem, not Gerit."""
    def __init__(self, count=12, initial_side=5.0):
        if count != 12:
            raise ValueError("This example supports exactly twelve unit squares")
        if initial_side < 4.0:
            raise ValueError("Fresh 4-by-3 separated start needs initial_side >= 4")
        self.count = count
        self.initial_side = initial_side

    objective_lower_bound = 0.0  # unused area cannot be negative (certified lower bound)

    def initial(self, rng):
        # A genuine valid 5-by-5 starting envelope when initial_side=5:
        # 4 columns, 3 rows; gaps keep the squares strictly non-overlapping.
        side=self.initial_side
        x_step=(side-1.)/3
        y_step=(side-1.)/2
        squares=tuple(Square(.5+i*x_step,.5+j*y_step,0.)
                      for j in range(3) for i in range(4))
        packing=Packing(squares,side)
        assert validate_packing(packing,tolerance=0.).valid
        return packing

    def evaluate(self, state):
        # Empty area is exactly L^2 - 12. Same minimizer as L and L^2.
        return state.container_side**2 - 12.0

    def feasible(self, state):
        return (isinstance(state,Packing) and len(state.squares)==self.count
                and validate_packing(state,tolerance=0.).valid)

    def distance(self,a,b):
        return packing_distance(a,b)

    def encode(self,state):
        return {'container_side':state.container_side,
                'squares':[{'x':s.x,'y':s.y,'angle':s.angle} for s in state.squares]}

    def decode(self,payload):
        return Packing(tuple(Square(**p) for p in payload['squares']),
                       float(payload['container_side']))


class PackingOperators:
    """Reuses the older Gerit geometric operators as swappable domain actions."""
    def __init__(self, *, cap_margin=.15, compression_attempts=8, rotation_attempts=12):
        if cap_margin < 0 or compression_attempts < 0 or rotation_attempts < 1:
            raise ValueError("cap-margin and compression-attempts must be nonnegative")
        self.learn_controller=LearningController()
        self.learn_policy=self.learn_controller.new_policy()
        self.learned_calls=0
        self.learned_improved=0
        self.rotation_attempts=rotation_attempts
        self.rotation_probes=0
        self.rotation_valid=0
        self.cap_margin=cap_margin
        self.compressor=CompressionSettings(attempts_per_child=max(1,compression_attempts))
        self.compression_attempts=compression_attempts

    def _finish(self,parent,raw,rng):
        if raw is None:
            return parent
        if self.compression_attempts:
            packed,_=compress_valid(raw,rng,self.compressor,
                                    side_cap=parent.container_side+self.cap_margin)
            return packed
        return raw

    def learned(self,parent,rng,intensity):
        """Reintegrate preexisting 10-family geometric policy learner.

        Note: shared adapter policy is a first integration, not yet a distinct
        inheritable policy for each independent generic-core lineage.
        """
        self.learned_calls+=1
        raw,metadata=propose_learned(parent,rng,
                      parent.container_side+self.cap_margin,
                      self.learn_policy,self.learn_controller)
        final=self._finish(parent,raw,rng)
        valid=(raw is not None and validate_packing(final,tolerance=0.).valid)
        raw_gain=(parent.container_side-raw.container_side) if raw is not None else 0.
        compression_gain=(raw.container_side-final.container_side) if raw is not None else 0.
        self.learn_policy,_=self.learn_controller.update(
            self.learn_policy,metadata,valid,raw_gain,
            compression_gain,parent.container_side)
        if valid and final.container_side < parent.container_side:
            self.learned_improved+=1
        return final

    def micro(self,parent,rng,intensity):
        # Legacy geometric operators accept a side cap, not an intensity.
        proposed,_=propose_micro(parent,rng,parent.container_side+self.cap_margin)
        return self._finish(parent,proposed,rng)

    def contact(self,parent,rng,intensity):
        proposed,_=propose_contact_relocate(parent,rng,
            parent.container_side+self.cap_margin,attempts=20)
        return self._finish(parent,proposed,rng)

    def restructure(self,parent,rng,intensity):
        proposed,_=propose_reconfigure(parent,rng,
                                      parent.container_side+self.cap_margin)
        return self._finish(parent,proposed,rng)

    def rotate(self,parent,rng,intensity):
        self.rotation_probes+=1
        trial=rotate_probe(parent,rng,intensity,cap_margin=self.cap_margin,
                           attempts=self.rotation_attempts)
        if trial is not parent:
            self.rotation_valid+=1
        return self._finish(parent,trial,rng)

    def compress(self,parent,rng,intensity):
        # Direct local search, including single-square and coordinated motions.
        settings=CompressionSettings(attempts_per_child=max(1,self.compression_attempts*2))
        packed,_=compress_valid(parent,rng,settings,
                                side_cap=parent.container_side+self.cap_margin)
        return packed


def main():
    parser=argparse.ArgumentParser(description="Gerit generic core + 12-square packing adapter")
    for item in fields(Settings):
        default=item.default
        flag="--"+item.name.replace("_","-")
        if isinstance(default,bool):
            parser.add_argument(flag,action="store_true",default=default)
        else:
            parser.add_argument(flag,type=type(default),default=default)
    parser.add_argument("--initial-side",type=float,default=5.)
    parser.add_argument("--operator-set",choices=("legacy-hybrid","basic"),default="legacy-hybrid")
    parser.add_argument("--cap-margin",type=float,default=.15)
    parser.add_argument("--compression-attempts",type=int,default=8)
    parser.add_argument("--rotation-attempts",type=int,default=12)
    parser.add_argument("--video",action="store_true",help="Save every generation as PNG frames and encode MP4")
    parser.add_argument("--fps",type=int,default=30)
    parser.add_argument("--image-width",type=int,default=900)
    parser.add_argument("--frame-every",type=int,default=1,help="Capture one frame every N generations")
    args=parser.parse_args()
    if args.maximize:
        parser.error("square packing minimizes container side: do not use --maximize")
    cfg=Settings(**{field.name:getattr(args,field.name) for field in fields(Settings)})
    problem=TwelveSquares(initial_side=args.initial_side)
    ops=PackingOperators(cap_margin=args.cap_margin,
                         compression_attempts=args.compression_attempts,
                         rotation_attempts=args.rotation_attempts)
    recorder=PackingRecorder(cfg.output_dir,args.initial_side,
                             video=args.video,fps=args.fps,
                             width=args.image_width,frame_every=args.frame_every)
    operators={'micro':ops.micro,'contact':ops.contact,
               'restructure':ops.restructure,'rotate':ops.rotate,
               'compress':ops.compress}
    if args.operator_set=="legacy-hybrid":
        operators['learned']=ops.learned
    print('GEOMETRY_OPERATORS',list(operators),flush=True)
    result=Search(problem,operators,cfg,on_generation=recorder).run()
    recorder.finish()
    side=result.best_state.container_side
    print("LEGACY_LEARNING",{"calls":ops.learned_calls,
                             "improving_candidates":ops.learned_improved,
                             "action_statistics":ops.learn_controller.snapshot()["observations"]},flush=True)
    print("ROTATION_PROBES",{"calls":ops.rotation_probes,
                            "valid_rotated_proposals":ops.rotation_valid},flush=True)
    print("ROTATION_STATISTICS",rotation_statistics(result.best_state),flush=True)
    print('DONE generations={} evaluations={} L={:.12f} area={:.12f} '
          'unused_area={:.12f} valid={} state={}'.format(
          result.generations,result.evaluations,side,side**2,
          result.best_objective,problem.feasible(result.best_state),
          (Path(cfg.output_dir)/"best.json").resolve()),flush=True)


if __name__=="__main__":
    main()
