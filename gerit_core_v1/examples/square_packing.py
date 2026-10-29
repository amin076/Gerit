"""N rigid unit squares in the smallest axis-aligned square, using generic Gerit.

Run from the repository's gerit_core_v1 directory:
  py -3 -m examples.square_packing --iterations 10000 --max-parents 10 ...
All domain geometry and mutation logic lives here; engine.py stays generic.
"""
from __future__ import annotations

import argparse
from dataclasses import fields
import math
import random
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


def default_initial_side(count):
    """Four times the grid reference area: side = 2 * ceil(sqrt(count))."""
    if not isinstance(count,int) or count < 1:
        raise ValueError("count must be a positive integer")
    return float(2 * math.ceil(math.sqrt(count)))


class UnitSquares:
    """Adapter: constraints and objective belong to THIS problem, not Gerit."""
    def __init__(self, count=12, initial_side=None, initial_mode="random",
                 random_angles=True, placement_attempts=2000, restart_attempts=200,
                 min_center_distance=2.0):
        if not isinstance(count,int) or count < 1:
            raise ValueError("count must be a positive integer")
        if initial_side is None:
            initial_side=default_initial_side(count)
        if initial_side <= 0 or not math.isfinite(initial_side):
            raise ValueError("initial_side must be positive and finite")
        if initial_mode not in ("random", "grid"):
            raise ValueError("initial_mode must be random or grid")
        if placement_attempts < 1 or restart_attempts < 1:
            raise ValueError("initial placement attempts and restarts must be positive")
        if initial_mode == "grid" and initial_side < 4.0:
            raise ValueError("grid initialization needs initial_side >= 4")
        if not math.isfinite(min_center_distance) or min_center_distance < math.sqrt(2):
            raise ValueError("min_center_distance must be >= sqrt(2) for guaranteed no overlap")
        self.min_center_distance=float(min_center_distance)
        self.count=count
        self.initial_side=float(initial_side)
        self.initial_mode=initial_mode
        self.random_angles=bool(random_angles)
        self.placement_attempts=placement_attempts
        self.restart_attempts=restart_attempts

    objective_lower_bound = 0.0  # unused area cannot be negative (certified lower bound)

    def initial(self, rng):
        if hasattr(self,"warm_start"):
            return self.warm_start

        """Start from feasible random positions and orientations, NOT a grid.

        Sequential rejection sampling validates each partial placement under
        the same strict collision and boundary rules used throughout search.
        No earlier solution is loaded and no special geometry is injected.
        """
        rng = rng if rng is not None else random.Random()
        side=self.initial_side
        if self.initial_mode == "grid":
            columns=math.ceil(math.sqrt(self.count))
            rows=math.ceil(self.count/columns)
            x_step=(side-1.)/max(1,columns-1)
            y_step=(side-1.)/max(1,rows-1)
            squares=tuple(Square(.5+(k%columns)*x_step,
                                 .5+(k//columns)*y_step,0.)
                          for k in range(self.count))
            packing=Packing(squares,side)
            if not self.feasible(packing):
                raise ValueError("Grid initial packing is invalid")
            return packing

        for _ in range(self.restart_attempts):
            placed=[]
            for _index in range(self.count):
                for _attempt in range(self.placement_attempts):
                    angle=rng.uniform(0.,math.pi/2) if self.random_angles else 0.
                    half_extent=.5*(abs(math.cos(angle))+abs(math.sin(angle)))
                    if 2*half_extent > side:
                        continue
                    square=Square(rng.uniform(half_extent,side-half_extent),
                                  rng.uniform(half_extent,side-half_extent),angle)
                    if any((square.x-prev.x)**2+(square.y-prev.y)**2
                           < self.min_center_distance**2 for prev in placed):
                        continue
                    trial=Packing(tuple(placed+[square]),side)
                    if validate_packing(trial,tolerance=0.).valid:
                        placed.append(square)
                        break
                else:
                    break
            if len(placed)==self.count:
                packing=Packing(tuple(placed),side)
                if self.feasible(packing):
                    return packing
        raise RuntimeError(
            f"Could not place {self.count} random squares within L={side}; "
            "increase --initial-side, lower --initial-min-center-distance "
            "(not below sqrt(2)), or increase --initial-restarts")

    def progress_display(self, state):
        """Human-readable square-side metric; the generic core is domain-agnostic."""
        return f"best_L={state.container_side:.12f}"

    def evaluate(self, state):
        # Empty area is exactly L^2 - count. Same minimizer as L and L^2.
        return state.container_side**2 - self.count

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

    def scaled_pose(self,parent,rng,intensity):
        """Intensity-aware domain move; the generic engine never sees x/y/angle."""
        if intensity<=0:
            return parent
        for _ in range(18):
            squares=list(parent.squares)
            index=rng.randrange(len(squares))
            old=squares[index]
            # A log-continuous displacement and rotation, both scaled by
            # the generic dimensionless intensity (including jump mode).
            magnitude=rng.uniform(.012,.16)*intensity
            angle_change=rng.uniform(-.12,.12)*intensity
            squares[index]=Square(old.x+rng.gauss(0,magnitude),
                                  old.y+rng.gauss(0,magnitude),
                                  old.angle+angle_change)
            raw=minimum_bounding_square(tuple(squares))
            if (raw.container_side<=parent.container_side+self.cap_margin
                    and validate_packing(raw,tolerance=0.).valid):
                return self._finish(parent,raw,rng)
        return parent

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
    parser=argparse.ArgumentParser(description="Gerit generic core + N-square packing adapter")
    for item in fields(Settings):
        default=item.default
        flag="--"+item.name.replace("_","-")
        if isinstance(default,bool):
            parser.add_argument(flag,action="store_true",default=default)
        else:
            parser.add_argument(flag,type=type(default),default=default)
    parser.add_argument("--square-count",type=int,default=12,
                        help="number of unit squares (default: 12; try 13)")
    parser.add_argument("--initial-side",type=float,default=None,
                        help="default: 2*ceil(sqrt(number_of_squares)); 8 for 12 squares")
    parser.add_argument("--initial-min-center-distance",type=float,default=2.,
                        help="minimum initial center distance in unit-square side lengths")
    parser.add_argument("--initial-mode",choices=("random","grid"),default="random")
    parser.add_argument("--initial-angle-mode",choices=("random","zero"),default="random")
    parser.add_argument("--initial-placement-attempts",type=int,default=2000)
    parser.add_argument("--initial-restarts",type=int,default=200)
    parser.add_argument("--initial-state",type=str,default=None,
                        help="path to prior best.json; load its full geometry, not a random start")
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
    problem=UnitSquares(count=args.square_count,initial_side=args.initial_side,
                          min_center_distance=args.initial_min_center_distance,
                          initial_mode=args.initial_mode,
                          random_angles=(args.initial_angle_mode=="random"),
                          placement_attempts=args.initial_placement_attempts,
                          restart_attempts=args.initial_restarts)
    if args.initial_state:
        source=Path(args.initial_state)
        payload=__import__("json").loads(source.read_text(encoding="utf8"))
        state=problem.decode(payload["state"] if "state" in payload else payload)
        if not problem.feasible(state):
            parser.error("The supplied initial-state geometry is invalid")
        problem.warm_start=state
        print("WARM_START",{"path":str(source.resolve()),
                            "side":state.container_side,
                            "empty_area":problem.evaluate(state)},flush=True)
    print("INITIAL_CONFIGURATION",{
        "square_count":problem.count,
        "mode":args.initial_mode,"side":problem.initial_side,
        "reference_side":math.ceil(math.sqrt(problem.count)),
        "min_center_distance":problem.min_center_distance,
        "angle_mode":args.initial_angle_mode,
        "placement_attempts":args.initial_placement_attempts,
        "restarts":args.initial_restarts},flush=True)
    ops=PackingOperators(cap_margin=args.cap_margin,
                         compression_attempts=args.compression_attempts,
                         rotation_attempts=args.rotation_attempts)
    recorder=PackingRecorder(cfg.output_dir, max(5.0,problem.warm_start.container_side+0.3) if args.initial_state else problem.initial_side,
                             video=args.video,fps=args.fps,
                             width=args.image_width,frame_every=args.frame_every)
    operators={'scaled_pose':ops.scaled_pose,'micro':ops.micro,'contact':ops.contact,
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
