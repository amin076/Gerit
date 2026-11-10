"""Kaggle Squares in Squares validator, scoring, inventory, and CSV exporter.

Independent of Gerit's evolutionary engine. Decimal strings are retained for
interval SAT checks; uncertain numerical contacts fail closed.
"""
from __future__ import annotations

import csv
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

import mpmath

MAX_N = 1000
COLUMNS = ("id", "n", "square_id", "x", "y", "angle")
DECIMAL = re.compile(r"[+-]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[eE][+-]?\d+)?\Z")


@dataclass(frozen=True)
class Candidate:
    n: int
    poses: tuple[tuple[str, str, str], ...]
    source: str
    reported_side: float | None = None


@dataclass(frozen=True)
class Check:
    valid: bool
    side: float | None
    reason: str


def decimal(value):
    if isinstance(value, bool) or not DECIMAL.fullmatch(str(value).strip()):
        raise ValueError(f"Not a decimal literal: {value!r}")
    s = str(value).strip()
    if not math.isfinite(float(s)):
        raise ValueError("Nonfinite decimal")
    return s


def grid_side(n):
    if type(n) is not int or not 1 <= n <= MAX_N:
        raise ValueError("n must be 1..1000")
    return math.isqrt(n - 1) + 1


def puzzle_score(n, side):
    grid_side(n)
    if not math.isfinite(side) or side <= 0:
        raise ValueError("Invalid side")
    return max(0., side / math.sqrt(n) - 1.)


def baseline_score(n):
    return puzzle_score(n, grid_side(n))


def baseline_total():
    return math.fsum(baseline_score(n) for n in range(1, MAX_N + 1))


def grid(n):
    width = grid_side(n)
    return Candidate(n, tuple((f"{i%width}.5", f"{i//width}.5", "0")
                              for i in range(n)), "grid", float(width))


def corners(x, y, a):
    c, s = mpmath.iv.cos(a), mpmath.iv.sin(a)
    h = mpmath.iv.mpf("0.5")
    return [(x+dx*c-dy*s, y+dx*s+dy*c)
            for dx,dy in ((-h,-h),(h,-h),(h,h),(-h,h))]


def pair_sat(a, b):
    """Certified disjointness, certified penetration, or undecidable."""
    sure_overlap_on_every_axis = True
    for vertices in (a,b):
        for k in (0,1):
            x0,y0=vertices[k]
            x1,y1=vertices[(k+1)%4]
            axis=(-(y1-y0),x1-x0)
            pa=[x*axis[0]+y*axis[1] for x,y in a]
            pb=[x*axis[0]+y*axis[1] for x,y in b]
            # A positive separating gap or exact boundary contact is valid.
            if max(v.b for v in pa)<=min(v.a for v in pb) or \
               max(v.b for v in pb)<=min(v.a for v in pa):
                return "separate"
            definitely_intersect=(
                min(max(v.a for v in pa),max(v.a for v in pb)) >
                max(min(v.b for v in pa),min(v.b for v in pb)))
            if not definitely_intersect:
                sure_overlap_on_every_axis=False
    return "overlap" if sure_overlap_on_every_axis else "uncertain"


def validate(candidate, *, check_reported=True):
    n = candidate.n
    if type(n) is not int or not 1 <= n <= MAX_N or len(candidate.poses) != n:
        return Check(False,None,"Incorrect number of squares")
    try:
        poses = [tuple(decimal(z) for z in sq) for sq in candidate.poses]
        if any(len(sq)!=3 for sq in poses):
            raise ValueError("Missing x/y/angle")
        floats=[tuple(float(z) for z in sq) for sq in poses]
        if any(abs(z)>1e6 for sq in floats for z in sq):
            raise ValueError("Out-of-range coordinate or angle")
    except (ValueError,TypeError,OverflowError) as exc:
        return Check(False,None,str(exc))
    # Exact half-integer lattice proof avoids millions of trig operations.
    if all(a==0 and (x-.5).is_integer() and (y-.5).is_integer()
           for x,y,a in floats):
        xy={(x,y) for x,y,_ in floats}
        if len(xy)!=n:
            return Check(False,None,"Duplicate grid cell")
        side=float(max(max(x for x,y in xy)-min(x for x,y in xy)+1,
                       max(y for x,y in xy)-min(y for x,y in xy)+1))
        kind="certified exact grid"
    else:
        # Broad-phase: circumscribed radius sqrt(2)/2, with extra margin.
        pending=[(i,j) for i in range(n) for j in range(i+1,n)
                 if abs(floats[i][0]-floats[j][0])<math.sqrt(2)+1e-9
                 and abs(floats[i][1]-floats[j][1])<math.sqrt(2)+1e-9]
        for dps in (50,100,200,500):
            if not pending:
                break
            mpmath.iv.dps=dps
            vs=[corners(*(mpmath.iv.mpf(z) for z in sq)) for sq in poses]
            undecided=[]
            for i,j in pending:
                outcome=pair_sat(vs[i],vs[j])
                if outcome=="overlap":
                    return Check(False,None,f"Overlapping squares {i},{j}")
                if outcome=="uncertain":
                    undecided.append((i,j))
            pending=undecided
        if pending:
            return Check(False,None,f"Uncertifiable contact {pending[0]}")
        with mpmath.workdps(80):
            extent=[]
            for x,y,a in poses:
                x,y,a=map(mpmath.mpf,(x,y,a))
                h=(abs(mpmath.cos(a))+abs(mpmath.sin(a)))/2
                extent.append((x-h,x+h,y-h,y+h))
            side=float(max(max(e[1] for e in extent)-min(e[0] for e in extent),
                           max(e[3] for e in extent)-min(e[2] for e in extent)))
        kind="certified interval SAT"
    if not math.isfinite(side) or side < math.sqrt(n)-1e-8:
        return Check(False,None,"Impossible enclosing side")
    if check_reported and candidate.reported_side is not None:
        side_given=float(candidate.reported_side)
        if not math.isfinite(side_given) or abs(side-side_given)>max(1e-8,2e-10*side):
            return Check(False,None,"Reported side differs from actual geometry")
    return Check(True,side,kind)


def scan(paths):
    """Read known Gerit JSON formats; scalar-only summaries are never poses."""
    best={}
    audit=[]
    files=[]
    for path in map(Path,paths):
        files.extend(sorted(path.rglob("*.json")) if path.is_dir() else [path])
    for path in files:
        try:
            obj=json.loads(path.read_text(encoding="utf-8"))
        except (OSError,ValueError):
            continue
        records=[]
        if isinstance(obj,dict):
            if isinstance(obj.get("best"),dict):
                records.append(obj["best"])
            for key in ("selected_members","members"):
                if isinstance(obj.get(key),list):
                    records.extend(obj[key])
            if isinstance(obj.get("squares"),list):
                records.append(obj)
        for index,item in enumerate(records):
            if not isinstance(item,dict) or not isinstance(item.get("squares"),list):
                continue
            label=f"{path}:{index}"
            try:
                poses=tuple((decimal(s["x"]),decimal(s["y"]),decimal(s["angle"]))
                            for s in item["squares"])
                cand=Candidate(len(poses),poses,label,item.get("container_side",item.get("side")))
                checked=validate(cand)
                audit.append({"source":label,"n":cand.n,"valid":checked.valid,
                              "measured_L":checked.side,"reported_L":cand.reported_side,
                              "reason":checked.reason})
                if checked.valid and (cand.n not in best or
                                      checked.side<validate(best[cand.n]).side):
                    best[cand.n]=cand
            except (KeyError,TypeError,ValueError) as exc:
                audit.append({"source":label,"valid":False,"reason":str(exc)})
        if not records and isinstance(obj,dict) and any(
                key in obj for key in ("best_side","best_L")):
            audit.append({"source":str(path),"valid":False,
                          "reason":"Scalar-only result, coordinates unavailable"})
    return best,audit


def improvements(candidates):
    chosen={}
    for n,c in candidates.items():
        if c.n!=n:
            raise ValueError("Candidate N/key mismatch")
        checked=validate(c)
        if checked.valid and checked.side<grid_side(n)-1e-9:
            chosen[n]=c
    return chosen


def export(path,candidates,*,complete):
    selected=improvements(candidates)
    valid={n:c for n,c in candidates.items() if n==c.n and validate(c).valid}
    ns=range(1,MAX_N+1) if complete else sorted(valid)
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    count=0
    with path.open("w",encoding="utf-8",newline="") as f:
        w=csv.writer(f)
        w.writerow(COLUMNS)
        for n in ns:
            candidate=(selected.get(n) or grid(n)) if complete else valid[n]
            for sid,(x,y,a) in enumerate(candidate.poses):
                w.writerow((count,n,sid,x,y,a))
                count+=1
    return count


def reimport(path):
    by_n={}
    with Path(path).open(encoding="utf-8",newline="") as f:
        rd=csv.DictReader(f)
        if tuple(rd.fieldnames or [])!=COLUMNS:
            raise ValueError("Invalid CSV header")
        for index,row in enumerate(rd):
            if int(row["id"])!=index:
                raise ValueError("Nonsequential row ID")
            n=int(row["n"])
            if not 1<=n<=MAX_N:
                raise ValueError("N outside 1..1000")
            poses=by_n.setdefault(n,[])
            if int(row["square_id"])!=len(poses):
                raise ValueError("Nonsequential square_id")
            poses.append(tuple(row[k] for k in ("x","y","angle")))
    if any(len(poses)!=n for n,poses in by_n.items()):
        raise ValueError("Incomplete puzzle rows")
    return {n:Candidate(n,tuple(poses),str(path)) for n,poses in by_n.items()}


def score_report(candidates,*,leader=22.0544214515):
    chosen=improvements(candidates)
    checked={n:validate(c) for n,c in candidates.items()}
    rows=[]
    for n in range(1,MAX_N+1):
        c=chosen.get(n)
        side=validate(c).side if c else float(grid_side(n))
        bs=baseline_score(n)
        score=puzzle_score(n,side)
        hist=checked.get(n)
        rows.append({"n":n,"gerit_L":hist.side if hist and hist.valid else None,
                     "baseline_L":grid_side(n),
                     "gerit_score":puzzle_score(n,hist.side) if hist and hist.valid else None,
                     "baseline_score":bs,"improvement":max(0.,bs-score),
                     "valid":bool(hist and hist.valid),"submitted_L":side,
                     "submitted_score":score,"source":c.source if c else "grid"})
    total=math.fsum(r["submitted_score"] for r in rows)
    baseline=baseline_total()
    return {"total_puzzles":MAX_N,"historical_N":len(candidates),
            "validated_N":sum(c.valid for c in checked.values()),
            "improved_N":len(chosen),"fallback_N":MAX_N-len(chosen),
            "grid_baseline":baseline,"score_improvement":baseline-total,
            "projected_score":total,"leader_reference":leader,
            "gap_to_leader":total-leader,"rows":rows}


def save_report(path,summary,audit):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({**summary,"inventory":audit},indent=2)+"\n",encoding="utf-8")
    with path.with_suffix(".csv").open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=summary["rows"][0].keys())
        writer.writeheader()
        writer.writerows(summary["rows"])
