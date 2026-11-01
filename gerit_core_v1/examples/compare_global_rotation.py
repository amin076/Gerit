"""Paired 1000-generation ablation: random 18-square start, rigid rotation OFF vs ON.

Run from gerit_core_v1:
    python -m examples.compare_global_rotation --generations 1000 --seed 4540

Both runs consume the SAME newly created randomized initial geometry; NEVER a grid.
Results are local outputs; this script does not change the generic Gerit engine.
"""
import argparse
import hashlib
import json
import random
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gerit.geometry import validate_packing, minimum_bounding_square
from examples.square_packing import UnitSquares


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--generations",type=int,default=1000)
    p.add_argument("--seed",type=int,default=4540)
    p.add_argument("--initial-side",type=float,default=12.0)
    p.add_argument("--out",default="results/global_rotation_ablation")
    args=p.parse_args()
    if args.generations<1 or args.initial_side<=0:
        p.error("generations must be positive and initial-side must be positive")
    root=Path(args.out).resolve()
    root.mkdir(parents=True,exist_ok=True)
    problem=UnitSquares(count=18,initial_side=args.initial_side,
                        initial_mode="random",random_angles=True,
                        min_center_distance=2.0,placement_attempts=2000,
                        restart_attempts=200)
    sampled=problem.initial(random.Random(args.seed))
    # Remove empty external margin for BOTH arms without rotating anything.
    # Otherwise the ON arm would receive an unfair free translation/shrink.
    initial=minimum_bounding_square(sampled.squares)
    assert validate_packing(initial,tolerance=0.).valid
    assert len(initial.squares)==18
    assert any(abs(s.angle)>1e-6 for s in initial.squares)
    assert len(set(round(s.angle,6) for s in initial.squares))>=17
    state={"state":problem.encode(initial),"metadata":{
        "purpose":"new independent random initial state shared by both arms",
        "square_count":18,"seed":args.seed,"initial_side":args.initial_side,
        "initial_mode":"random","initial_angle_mode":"random",
        "initial_min_center_distance":2.0,
        "sampled_container_side":sampled.container_side,
        "tight_container_side_before_any_rotation":initial.container_side}}
    encoded=json.dumps(state,sort_keys=True,indent=2).encode("utf8")
    initial_path=root/"random_generation_zero.json"
    initial_path.write_bytes(encoded)
    fingerprint=hashlib.sha256(encoded).hexdigest()
    print("VERIFIED_RANDOM_INITIAL",initial_path,"sha256",fingerprint,flush=True)
    print("GENERATION_ZERO_ANGLES",[round(s.angle,5) for s in initial.squares],flush=True)

    results={}
    for enabled,label in ((False,"without_rotation"),(True,"with_rotation")):
        output=root/label
        cmd=[sys.executable,"-m","examples.square_packing",
             "--iterations",str(args.generations),
             "--square-count","18",
             "--initial-mode","random",
             "--initial-angle-mode","random",
             "--initial-side",str(args.initial_side),
             "--initial-min-center-distance","2",
             "--initial-state",str(initial_path),
             "--children-per-parent","10",
             "--initial-parents","1",
             "--max-parents","4",
             "--adaptive-historical",
             "--max-forward-branches","2",
             "--max-historical-branches","2",
             "--fair-historical-budget",
             "--historical-forward-reserve","2",
             "--evaluation-budget","350000",
             "--checkpoint-every","10",
             "--log-every","50",
             "--seed",str(args.seed),
             "--output-dir",str(output)]
        if enabled:
            cmd.append("--global-rotation")
        print("START_ARM",label,flush=True)
        start=time.perf_counter()
        with (root/(label+".log")).open("w",encoding="utf8") as log:
            subprocess.run(cmd,check=True,stdout=log,stderr=subprocess.STDOUT)
        elapsed=time.perf_counter()-start
        stats=json.loads((output/"global_rotation_stats.json").read_text(encoding="utf8"))
        best=json.loads((output/"best.json").read_text(encoding="utf8"))
        results[label]={"wall_seconds":elapsed,"best_L":best["state"]["container_side"],
                        "best_objective":best["objective"],
                        "evaluations":stats["evaluations"],
                        "generations":stats["generation"],
                        "rotation_calls":stats["calls"],
                        "rotation_seconds":stats["seconds"],
                        "log":str(root/(label+".log"))}
        print("FINISHED_ARM",label,results[label],flush=True)
    off,on=results["without_rotation"],results["with_rotation"]
    report={"random_initial_sha256":fingerprint,"initial_state_path":str(initial_path),
            "seed":args.seed,"generations_requested":args.generations,"runs":results,
            "delta_L_off_minus_on":off["best_L"]-on["best_L"],
            "wall_time_ratio_on_over_off":on["wall_seconds"]/max(off["wall_seconds"],1e-9),
            "rotation_overhead_fraction_of_on_wall":on["rotation_seconds"]/max(on["wall_seconds"],1e-9),
            "important":"A single seed is not statistical proof. Equal generations do not imply exactly equal evaluations."}
    (root/"comparison.json").write_text(json.dumps(report,indent=2),encoding="utf8")
    print("COMPARISON",json.dumps(report,indent=2),flush=True)


if __name__=="__main__":
    main()
