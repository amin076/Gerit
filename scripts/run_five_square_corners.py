"""Run reproducible 5-square corner-center search trials; preserve all poses."""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import asdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from experiments.five_squares.optimizer import corner_center_seed,search,to_json
from gerit.geometry import square_vertices
from gerit.kaggle import Candidate,validate,export,puzzle_score,baseline_score


def svg_packing(packing):
    """Static reproducible geometric SVG with actual unit-square vertices."""
    palette=["#85b8e6","#b3dca6","#f4ba90","#d2b9ea","#e5bd58"]
    side=packing.container_side
    scale=360/side
    parts=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 420 440">',
           '<rect width="420" height="440" fill="white"/>',
           f'<text x="210" y="27" text-anchor="middle" font-size="16">N=5, L={side:.10f}</text>',
           '<rect x="30" y="45" width="360" height="360" fill="none" stroke="#222" stroke-width="2"/>']
    for i,s in enumerate(packing.squares):
        vertices=square_vertices(s)
        coords=" ".join(f"{30+x*scale:.6f},{405-y*scale:.6f}" for x,y in vertices)
        parts.append(f'<polygon points="{coords}" fill="{palette[i]}" fill-opacity="0.85" stroke="#333" stroke-width="1.1"/>')
    parts.append(f'<text x="210" y="430" text-anchor="middle" font-size="13">Four corner squares + rotating central square</text>')
    parts.append('</svg>')
    return "\n".join(parts)+"\n"


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--seeds",nargs="+",type=int,default=[2715,2716,2717])
    parser.add_argument("--proposals",type=int,default=250)
    parser.add_argument("--out",type=Path,default=Path("results/five-square-corner-center"))
    args=parser.parse_args()
    if args.out.exists():
        raise FileExistsError(f"Won't overwrite experiment history: {args.out}")
    baseline=corner_center_seed()
    assert baseline.container_side==3.0
    args.out.mkdir(parents=True)
    (args.out/"initial_seed.json").write_text(
        json.dumps({"n":5,"side":3.,"squares":[asdict(s) for s in baseline.squares]},indent=2)+"\n")
    (args.out/"initial_seed.svg").write_text(svg_packing(baseline))
    trial_results=[]
    for seed in args.seeds:
        result=search(seed=seed,proposals=args.proposals)
        (args.out/f"trial_{seed}.json").write_text(json.dumps(to_json(result),indent=2)+"\n")
        trial_results.append(result)
    best=min(trial_results,key=lambda r:r.best.container_side)
    poses=tuple((repr(s.x),repr(s.y),repr(s.angle)) for s in best.best.squares)
    candidate=Candidate(5,poses,"five_square_coordinated_search",best.best.container_side)
    check=validate(candidate)
    if not check.valid:
        raise RuntimeError("Independent high-precision validation failed: "+check.reason)
    if abs(check.side-best.best.container_side)>1e-8:
        raise RuntimeError("Side length differs between validators")
    record=to_json(best)
    (args.out/"best_result.json").write_text(json.dumps(record,indent=2)+"\n")
    (args.out/"best.svg").write_text(svg_packing(best.best))
    rows=export(args.out/"five_square_partial.csv",{5:candidate},complete=False)
    if rows!=5:
        raise AssertionError("Expected exactly five submission rows")
    comparison={
        "n":5,"baseline_side":3.,"gerit_side":check.side,
        "baseline_score":baseline_score(5),
        "gerit_score":puzzle_score(5,check.side),
        "score_improvement":baseline_score(5)-puzzle_score(5,check.side),
        "valid":check.valid,"validation":check.reason,
        "winner_seed":best.seed,"trials":len(trial_results),
        "total_proposals":sum(r.proposals for r in trial_results),
        "results":[{"seed":r.seed,"side":r.best.container_side,
                    "improvements":r.accepted_improvements} for r in trial_results],
    }
    (args.out/"comparison.json").write_text(json.dumps(comparison,indent=2)+"\n")
    with (args.out/"trial_results.csv").open("w",newline="") as f:
        w=csv.writer(f);w.writerow(["seed","proposals","side","angle","inward"])
        for r in trial_results:
            w.writerow([r.seed,r.proposals,r.best.container_side,r.best_angle,r.best_inward])
    print(json.dumps(comparison,indent=2))


if __name__=="__main__":
    main()
