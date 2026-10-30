"""Audit whether historical backtracking lies on the exact final winner ancestry.

Usage: py -3 -m examples.analyze_historical_ancestry --output-dir results/...
Works with old malformed \\n-separated genealogy and valid JSONL.
"""
import argparse
import json
from collections import Counter
from pathlib import Path


def read_records(path):
    raw=Path(path).read_text(encoding="utf8")
    decoder=json.JSONDecoder()
    offset=0
    while offset<len(raw):
        while offset<len(raw) and raw[offset].isspace():
            offset+=1
        if raw.startswith(chr(92)+"n",offset):
            offset+=2
            continue
        if offset>=len(raw):
            break
        row,end=decoder.raw_decode(raw,offset)
        if not isinstance(row,dict):
            raise ValueError("Non-object record in genealogy")
        yield row
        offset=end


def analyze(output):
    output=Path(output)
    summary=json.loads((output/"run_summary.json").read_text(encoding="utf8"))
    best=json.loads((output/"best.json").read_text(encoding="utf8"))
    nodes={row["node_id"]:row for row in read_records(output/"genealogy.jsonl")}
    cursor=best["best_node_id"]
    ancestry=[]
    seen=set()
    while cursor is not None:
        if cursor in seen or cursor not in nodes:
            raise ValueError(f"Genealogy cycle or incomplete ancestor: {cursor}")
        seen.add(cursor)
        row=nodes[cursor]
        ancestry.append(row)
        cursor=row["parent_node_id"]
    ancestry.reverse()
    ancestor_ids={row["node_id"] for row in ancestry}
    spawns=[event for event in summary["events"] if event.get("event")=="historical_spawn"]
    historical_seeds=[event for event in spawns if event.get("seed_node_id") in ancestor_ids]
    records=[event for event in summary["events"] if event.get("event")=="best_record"]
    born_by_lineage={event["lineage_id"]:event for event in summary["events"]
                     if event.get("event") in ("historical_spawn","population_expand","explorer_spawn")
                     and event.get("lineage_id") is not None}
    counts=Counter(event["lineage_id"] for event in records)
    print("BEST_NODE",best["best_node_id"])
    print("BEST_ORIGIN_LINEAGE",best.get("origin",{}).get("lineage_id"))
    print("ANCESTOR_NODES",len(ancestry))
    print("HISTORICAL_SPAWNS_TOTAL",len(spawns))
    print("HISTORICAL_SEED_ON_FINAL_ANCESTRY",len(historical_seeds))
    for event in historical_seeds:
        print("HISTORICAL_ANCESTOR",json.dumps({
            key:event.get(key) for key in ("lineage_id","generation",
                                           "from_generation","rollback_generations",
                                           "seed_node_id")},ensure_ascii=False))
    print("BEST_RECORDS_BY_LINEAGE",json.dumps(dict(counts.most_common()),ensure_ascii=False))
    final_lineage=best.get("origin",{}).get("lineage_id")
    print("FINAL_LINEAGE_BIRTH_EVENT",
          json.dumps(born_by_lineage.get(final_lineage),ensure_ascii=False))
    if not historical_seeds:
        print("NOTE: A historical branch can influence search indirectly without being a direct ancestor.")
        print("NOTE: Historic-source nodes can be shared with ordinary branches; causal attribution needs ablation.")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output-dir",required=True)
    args=parser.parse_args()
    analyze(args.output_dir)


if __name__=="__main__":
    main()
