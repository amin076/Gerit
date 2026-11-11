"""Append-only method provenance for geometrical Kaggle experiments.

A registry winner contains source/operator/experiment_id already; this ledger
records both accepted and rejected candidates and the precise search settings.
Single-process writer, matching the single-process best registry semantics.
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def record_attempt(path, *, n, family, script, algorithm, seed, parameters,
                   before_side, candidate_side, valid, validation, accepted,
                   experiment_id, generation=0, note=""):
    if not family or not script or not algorithm or not experiment_id:
        raise ValueError("Method provenance fields must not be empty")
    identity = {
        "n": n, "family": family, "script": script, "algorithm": algorithm,
        "seed": seed, "parameters": parameters, "candidate_side": candidate_side,
        "experiment_id": experiment_id, "generation": generation,
    }
    fingerprint = hashlib.sha256(
        json.dumps(identity, sort_keys=True, ensure_ascii=False,
                   separators=(",", ":")).encode("utf-8")).hexdigest()
    event = {
        "schema_version": 1, "event_id": fingerprint,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        **identity,
        "previous_side": before_side,
        "valid": bool(valid), "validation": str(validation),
        "accepted": bool(accepted), "note": note,
    }
    dst = Path(path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False, sort_keys=True,
                           allow_nan=False) + "\n")
    return event


def summarize_ledger(path, csv_path):
    path = Path(path)
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
               if line.strip()] if path.exists() else []
    cols = ["family", "evaluated", "valid", "accepted", "best_candidate_side"]
    groups = {}
    for row in records:
        item = groups.setdefault(row["family"], {
            "family": row["family"], "evaluated": 0, "valid": 0,
            "accepted": 0, "best_candidate_side": None})
        item["evaluated"] += 1
        item["valid"] += bool(row["valid"])
        item["accepted"] += bool(row["accepted"])
        if row["valid"]:
            side = row["candidate_side"]
            item["best_candidate_side"] = (
                side if item["best_candidate_side"] is None
                else min(item["best_candidate_side"], side))
    dst = Path(csv_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        writer.writerows(groups[name] for name in sorted(groups))
    return list(groups.values())
