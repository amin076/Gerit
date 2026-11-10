"""Build complete and partial Kaggle CSV submissions from actual Gerit runs."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from gerit.kaggle import (scan,export,reimport,validate,score_report,save_report,
                          grid_side)


def main():
    parser=argparse.ArgumentParser(description="Gerit Kaggle submission builder")
    parser.add_argument("--sources",nargs="+",default=["data","results"],
                        help="Existing Gerit output directories / JSON files")
    parser.add_argument("--out",default="kaggle_output")
    parser.add_argument("--leader",type=float,default=22.0544214515,
                        help="Reference from 2026-11-10 screenshot; not live")
    parser.add_argument("--full-recheck",action="store_true",
                        help="Independently recheck all 1000 exported puzzles")
    a=parser.parse_args()
    candidates,audit=scan(a.sources)
    out=Path(a.out)
    partial_rows=export(out/"submission_partial.csv",candidates,complete=False)
    full_rows=export(out/"submission_complete.csv",candidates,complete=True)
    partial=reimport(out/"submission_partial.csv")
    complete=reimport(out/"submission_complete.csv")
    if len(complete)!=1000 or full_rows!=500500 or \
       sum(len(c.poses) for c in complete.values())!=500500:
        raise RuntimeError("Full submission row count incorrect")
    if partial_rows!=sum(len(c.poses) for c in partial.values()):
        raise RuntimeError("Partial submission row count incorrect")
    required=complete if a.full_recheck else {
        n:complete[n] for n in (1,2,5,12,17,100,1000)}
    for n,c in [*required.items(),*partial.items()]:
        result=validate(c)
        if not result.valid:
            raise RuntimeError(f"CSV N={n} failed: {result.reason}")
    summary=score_report(candidates,leader=a.leader)
    save_report(out/"competition_report.json",summary,audit)
    print(json.dumps({k:v for k,v in summary.items() if k!="rows"} |
                     {"partial_rows":partial_rows,"complete_rows":full_rows,
                      "inventoried_records":len(audit),"full_recheck":a.full_recheck},
                     indent=2))


if __name__=="__main__":
    main()
