"""Summarize independent Gerit fresh-start square packing experiments.

Usage:
  py -3 -m examples.summarize_multiseed --results-root results --include-seed 4535
"""
import argparse
import csv
import json
import math
import statistics
from pathlib import Path


def summarize_folder(folder):
    summary=json.loads((folder/"run_summary.json").read_text(encoding="utf8"))
    best=json.loads((folder/"best.json").read_text(encoding="utf8"))
    events=summary.get("events",[])
    historical=[e for e in events if e.get("event")=="historical_spawn"]
    records=[e for e in events if e.get("event")=="best_record"]
    direct_historical=sum(1 for e in records if e.get("historical_origin_lineage_id",0))
    return {
        "seed":summary["settings"]["seed"],
        "generations":summary["generation"],
        "evaluations":summary["evaluations"],
        "best_L":best["state"]["container_side"],
        "initial_side":8.0,
        "max_parents":summary["settings"]["max_parents"],
        "historical_spawned":len(historical),
        "historical_promoted":summary.get("historical_stats",{}).get("promoted",0),
        "historical_expired":summary.get("historical_stats",{}).get("expired",0),
        "record_events_with_historical_origin":direct_historical,
        "final_historical_origin_lineage_id":best.get("origin",{}).get("historical_origin_lineage_id",0),
        "folder":str(folder)
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--results-root",default="results")
    parser.add_argument("--include-seed",type=int,default=None,
                        help="Include a previously completed compatible fresh-start seed")
    args=parser.parse_args()
    root=Path(args.results_root)
    seeds=[4536,4537,4538,4539,4540]
    if args.include_seed is not None:
        seeds.insert(0,args.include_seed)
    rows=[]
    for seed in seeds:
        folder=root/f"squares-18-fresh8-p4-g3000-{seed}"
        if not (folder/"run_summary.json").is_file() or not (folder/"best.json").is_file():
            print(f"MISSING seed {seed}: {folder}")
            continue
        item=summarize_folder(folder)
        if item["generations"]!=3000 or item["initial_side"]!=8 or item["max_parents"]!=4:
            raise ValueError(f"Unexpected experiment settings: {folder}")
        rows.append(item)
    if not rows:
        raise SystemExit("No completed runs found")
    destination=root/"four_branch_multiseed_summary.csv"
    with destination.open("w",newline="",encoding="utf8") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    values=[r["best_L"] for r in rows]
    print(f"RUNS {len(rows)}")
    for r in rows:
        print(f"seed={r['seed']} L={r['best_L']:.12f} evals={r['evaluations']}"
              f" historical_spawns={r['historical_spawned']}"
              f" historical_origin_final={r['final_historical_origin_lineage_id']}")
    print(f"MEAN_L {statistics.mean(values):.12f}")
    print(f"MEDIAN_L {statistics.median(values):.12f}")
    print(f"MIN_L {min(values):.12f}")
    print(f"MAX_L {max(values):.12f}")
    print(f"STD_L {statistics.stdev(values):.12f}" if len(values)>1 else "STD_L unavailable")
    print(f"CSV {destination.resolve()}")
    print("WARNING: these are equal-generation runs; evaluation counts may differ.")


if __name__=="__main__":
    main()
