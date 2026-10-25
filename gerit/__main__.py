"""Gerit command-line driver: inspect config or run a real evolutionary search."""
from __future__ import annotations
import argparse
import json
from dataclasses import asdict
from .config import load_config
from .evolution import evolve

def main() -> None:
    parser=argparse.ArgumentParser(description="Gerit rigid-square evolutionary search")
    parser.add_argument("--config",default="configs/five-squares.json")
    parser.add_argument("--dry-run",action="store_true",help="Validate configuration without searching")
    parser.add_argument("--output",default="results/five-squares-latest.json",help="Best-result JSON output")
    parser.add_argument("--runs-dir",default="results",help="Root for auditable run directories")
    parser.add_argument("--image-columns",type=int,default=5,help="Population mosaic columns")
    parser.add_argument("--adaptive",action="store_true",help="Enable density- and acceptance-adaptive mutation")
    parser.add_argument("--coordinated",action="store_true",help="Use simultaneous multi-square mutation")
    parser.add_argument("--compression",action="store_true",help="Compress every valid coordinated child")
    args=parser.parse_args()
    config=load_config(args.config)
    if args.dry_run:
        print(json.dumps({"status":"configuration_only","config":asdict(config),
                          "selection_slots":config.selection_slots(),
                          "first_generation_child_proposals":config.initial_population*config.offspring_per_parent,
                          "later_generation_child_proposals":config.next_generation_population*config.offspring_per_parent},
                         ensure_ascii=False,indent=2))
        return
    result=evolve(config,output_dir=args.runs_dir,image_columns=args.image_columns,adaptive=args.adaptive,coordinated=args.coordinated,compression=args.compression)
    result.save(args.output)
    print(json.dumps({"status":"completed","best_side":result.best.container_side,
                      "unused_area":result.best.container_side**2-config.n_squares,
                      "evaluations":result.evaluations,"generations":len(result.history)-1,
                      "output":args.output,"audit_root":args.runs_dir},ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
