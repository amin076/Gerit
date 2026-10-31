"""Two identical fresh 20-generation OFF runs to audit deterministic replay.

Uses the paired experiment's exact verified initial-state generator via an
initial-only helper in this file. Excludes wall-clock timings from comparison.
"""
from __future__ import annotations
import argparse
import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path

from gerit.geometry import minimum_bounding_square, validate_packing
from examples.square_packing import UnitSquares


def run_audit(*, seed=4540, generations=20, out="results/rotation_replay_audit"):
    root=Path(out).resolve()
    root.mkdir(parents=True,exist_ok=True)
    problem=UnitSquares(count=18,initial_side=12.,initial_mode="random",
                        random_angles=True,min_center_distance=2.,
                        placement_attempts=2000,restart_attempts=200)
    initial=minimum_bounding_square(problem.initial(random.Random(seed)).squares)
    if not validate_packing(initial,tolerance=0.).valid:
        raise AssertionError("Shared starting geometry is invalid")
    initial_path=root/"initial.json"
    initial_path.write_text(json.dumps({"state":problem.encode(initial)},sort_keys=True),encoding="utf8")
    outputs=[]
    for trial in (1,2):
        dest=root/f"repeat_{trial}"
        cmd=[sys.executable,"-m","examples.square_packing",
             "--iterations",str(generations),"--square-count","18",
             "--initial-side","12","--initial-state",str(initial_path),
             "--children-per-parent","10","--initial-parents","1","--max-parents","4",
             "--adaptive-historical","--max-forward-branches","2",
             "--max-historical-branches","2","--fair-historical-budget",
             "--historical-forward-reserve","2","--evaluation-budget","350000",
             "--checkpoint-every","10","--log-every","50","--seed",str(seed),
             "--output-dir",str(dest)]
        with (root/f"repeat_{trial}.log").open("w",encoding="utf8") as log:
            subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
        best=json.loads((dest/"best.json").read_text(encoding="utf8"))
        stat=json.loads((dest/"global_rotation_stats.json").read_text(encoding="utf8"))
        outputs.append({"state":best["state"],"objective":best["objective"],
                        "evaluations":stat["evaluations"],"generations":stat["generation"]})
    identical=outputs[0]==outputs[1]
    report={"seed":seed,"generations":generations,"identical":identical,
            "outputs":outputs}
    (root/"reproducibility.json").write_text(json.dumps(report,indent=2),encoding="utf8")
    print("REPRODUCIBILITY",{"identical":identical,"seed":seed,
                             "generations":generations,
                             "side_1":outputs[0]["state"]["container_side"],
                             "side_2":outputs[1]["state"]["container_side"],
                             "evaluations_1":outputs[0]["evaluations"],
                             "evaluations_2":outputs[1]["evaluations"]},flush=True)
    if not identical:
        raise AssertionError("Identical version, start and seed diverged; inspect reproducibility.json")
    return report


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--seed",type=int,default=4540)
    p.add_argument("--generations",type=int,default=20)
    p.add_argument("--out",default="results/rotation_replay_audit")
    a=p.parse_args()
    run_audit(seed=a.seed,generations=a.generations,out=a.out)
