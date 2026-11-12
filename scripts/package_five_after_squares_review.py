"""Create a compact, read-only review archive for the 50-case Gerit experiment.

Includes the actual 1000-case bank, family sweep states, and the exact
winner JSON files referenced by those states. Excludes huge near-NPZs,
generational logs, and irrelevant historical runs. No registry mutation.
"""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_archive(*,root=ROOT,output=None,first_k=22,last_k=31):
    root=Path(root).resolve()
    output=Path(output or root/"kaggle_output"/"gerit_review_50_cases.zip").resolve()
    bank=root/"results"/"kaggle_baseline"/"best_registry.json"
    if not bank.is_file():
        raise FileNotFoundError(f"Missing bank: {bank}")
    files={bank}
    summary=[]
    for k in range(first_k,last_k+1):
        low=k*k+1
        high=low+4
        directory=root/"results"/"kaggle_auto"/"five_after_squares_k22_31"/f"k{k:02d}_n{low}_{high}"
        statefile=directory/"sweep_state.json"
        if not statefile.exists():
            summary.append({"k":k,"range":[low,high],"completed":0,
                            "improved":0,"status":"not_started"})
            continue
        files.add(statefile)
        state=json.loads(statefile.read_text(encoding="utf-8"))
        results=state.get("results",[])
        if state.get("next_index")!=len(results):
            raise ValueError(f"Inconsistent checkpoint: {statefile}")
        count=0
        for row in results:
            if not row.get("better"):
                continue
            count+=1
            best_file=row.get("best_file")
            if not best_file:
                raise ValueError(f"Missing best_file N={row.get('n')}")
            file=Path(best_file)
            if not file.is_absolute():
                file=root/file
            file=file.resolve()
            if not file.is_relative_to(root) or not file.is_file():
                raise FileNotFoundError(f"Invalid or missing winner file: {file}")
            files.add(file)
        summary.append({"k":k,"range":[low,high],"completed":len(results),
                        "improved":count,"status":"complete" if len(results)==5 else "partial",
                        "projected_score":state.get("projected_score")})
    data=json.loads(bank.read_text(encoding="utf-8"))
    overview={"registry_score":data["total_score"],
              "improved_in_bank":sum(v["side"]<v["baseline_side"]-1e-10
                                     for v in data["problems"].values()),
              "families":summary,
              "total_completed":sum(x["completed"] for x in summary),
              "total_improved":sum(x["improved"] for x in summary)}
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite: {output}")
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,"x",compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6) as archive:
        archive.writestr("review_overview.json",
                         json.dumps(overview,indent=2,ensure_ascii=False))
        for file in sorted(files):
            archive.write(file,file.relative_to(root).as_posix())
    print(json.dumps(overview,indent=2,ensure_ascii=False))
    print(f"REVIEW_ARCHIVE {output} FILES={len(files)+1}")
    return overview


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",default=None)
    p.add_argument("--first-k",type=int,default=22)
    p.add_argument("--last-k",type=int,default=31)
    args=p.parse_args()
    build_archive(output=args.output,first_k=args.first_k,last_k=args.last_k)


if __name__=="__main__":
    main()
