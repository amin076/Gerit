"""Strict JSON packing loader with a narrow legacy newline repair.

An early Gerit growth writer appended the literal two characters '\\n'
after a complete JSON object. This function accepts ONLY that known
suffix (possibly repeated) or ordinary whitespace, not arbitrary
concatenated JSON or damaged geometries. Validation is done by caller.
"""
from __future__ import annotations
import json
from pathlib import Path


def load_packing_json(path):
    content=Path(path).read_text(encoding="utf-8-sig")
    decoder=json.JSONDecoder()
    item,end=decoder.raw_decode(content.lstrip())
    tail=content.lstrip()[end:]
    remaining=tail.strip()
    if remaining:
        if remaining.replace("\\n","").strip():
            raise ValueError(
                f"Unexpected non-whitespace after JSON object in {path}; "
                "refusing to guess which packing to use")
    if not isinstance(item,dict) or not all(
        key in item for key in ("n","side","squares")
    ):
        raise ValueError(f"Missing n/side/squares in packing JSON: {path}")
    if not isinstance(item["squares"],list):
        raise ValueError("Expected list of square poses")
    return item
