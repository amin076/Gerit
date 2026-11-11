"""Retry 228 from the certified 227 founder and repair near-feasible states.

Does not alter the official Gerit registry unless --apply is supplied.
The best *invalid* checkpoint is stored separately so future refinements
can continue rather than randomly restart from the same source.
"""
from __future__ import annotations
import argparse,json,math,sys
from dataclasses import asdict
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from gerit.elastic_growth import initial_growth_pose,relax_once,certified_candidate
from gerit.elastic_repair import feasibility_diagnostics,repair_relaxation
from gerit.geometry import Packing,Square
from gerit.kaggle import Candidate,validate
from scripts.kaggle_best_registry import read_registry,propose_improvement

def run(registry,*,n=228,attempts=24,iterations=500,seed=102,
        apply=False,report=None,checkpoint=None,report_every=5,
        source_file=None,best_file=None):
    if not 2<=n<=1000 or attempts<1 or iterations<1:
        raise ValueError("Invalid search parameters")
    if report and Path(report).exists():
        raise FileExistsError("Refusing to overwrite report")
    if checkpoint and Path(checkpoint).exists():
        raise FileExistsError("Refusing to overwrite checkpoint")
    if best_file and Path(best_file).exists():
        raise FileExistsError("Refusing to overwrite best candidate file")
    bank=read_registry(registry)
    entry=(json.loads(Path(source_file).read_text(encoding="utf-8"))
           if source_file else bank["problems"][str(n-1)])
    if int(entry["n"])!=n-1:
        raise ValueError("Source packing N does not match n-1")
    source=Packing(tuple(Square(float(s["x"]),float(s["y"]),float(s["angle"]))
                         for s in entry["squares"]),float(entry["side"]))
    # Certify an externally supplied best packing before using it as a founder.
    from gerit.geometry import validate_packing
    if not validate_packing(source,tolerance=0.).valid:
        raise ValueError("Source packing failed strict SAT validation")
    if source_file:
        founder_check=validate(Candidate(n-1,tuple((repr(s.x),repr(s.y),repr(s.angle))
                                             for s in source.squares),
                                        "elastic_source_file",source.container_side))
        if not founder_check.valid:
            raise ValueError(f"Independent source validation failed: {founder_check.reason}")
    current=float(bank["problems"][str(n)]["side"])
    cap=current-.0005
    if cap<=math.sqrt(n):
        raise ValueError("Impossible cap")
    rng=np.random.default_rng(seed)
    best=None
    nearest=None
    best_violation=float("inf")
    records=[]
    print(f"BEGIN N={n} from={n-1} source_L={source.container_side:.12f} cap={cap:.9f}",flush=True)
    for k in range(attempts):
        initial=initial_growth_pose(source,rng,cap,randomize_count=0)
        pose,energy,_=relax_once(initial,cap,iterations=iterations,
                                  penalty_schedule=(1,10,100,1000),
                                  angle_weight=2e-5)
        before=feasibility_diagnostics(pose,cap)
        # Always repair the promising state, not the original founder.
        repaired,repair_energy,_=repair_relaxation(pose,cap,iterations=max(200,iterations//2))
        after=feasibility_diagnostics(repaired,cap)
        violation=after["total_penetration"]+after["boundary_total"]
        if violation<best_violation:
            nearest=repaired.copy()
            best_violation=violation
        candidate=certified_candidate(repaired,cap)
        certification="strict SAT rejected"
        if candidate:
            verdict=validate(Candidate(n,tuple((repr(s.x),repr(s.y),repr(s.angle))
                                        for s in candidate.squares),
                                       "elastic_repair_continuation",candidate.container_side))
            certification=verdict.reason
            if verdict.valid and (best is None or candidate.container_side<best.container_side):
                best=candidate
                print(f"CERTIFIED attempt={k+1} L={best.container_side:.12f}",flush=True)
        records.append({"attempt":k+1,"initial_loss":energy,"repair_loss":repair_energy,
                        "before":before,"after":after,"certification":certification})
        if (k+1)%report_every==0 or k+1==attempts:
            print(f"TRIAL {k+1}/{attempts} overlaps={after['overlap_pairs']} "
                  f"max_penetration={after['max_penetration']:.3g} "
                  f"outside={after['outside_squares']} "
                  f"best_certified_L={(best.container_side if best else float('nan')):.12f}",
                  flush=True)
    accepted=False
    if best and apply:
        accepted=bool(propose_improvement(
            registry,{"n":n,"side":best.container_side,
                      "squares":[asdict(s) for s in best.squares]},
            source="gerit_elastic_repair",experiment_id=f"elastic-repair-n{n}-seed{seed}",
            generation=attempts,operator="elastic_collective_repair")["accepted"])
    elif best:
        accepted=True
    if best_file and best is not None:
        output=Path(best_file)
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps({"n":n,"side":best.container_side,
                                     "squares":[asdict(s) for s in best.squares]},
                                     indent=2)+"\n",encoding="utf-8")
    result={"n":n,"source_n":n-1,"source_side":source.container_side,
            "source_file":str(source_file) if source_file else None,
            "best_file":str(best_file) if best_file and best else None,
            "previous_side":current,"best_certified_side":best.container_side if best else None,
            "accepted":accepted,"applied":apply,"attempts":attempts,
            "initial_score":bank["total_score"],
            "final_score":(read_registry(registry)["total_score"] if apply else
                           float(bank["total_score"])+(best.container_side-current)/math.sqrt(n)
                           if accepted else bank["total_score"]),
            "best_invalid_total_violation":best_violation,"records":records}
    if report:
        out=Path(report);out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    if checkpoint and nearest is not None:
        out=Path(checkpoint);out.parent.mkdir(parents=True,exist_ok=True)
        np.savez_compressed(out,poses=nearest,side_cap=np.array(cap),
                            source_n=np.array(n-1),target_n=np.array(n),seed=np.array(seed))
    print(f"FINISHED n={n} certified={best is not None} accepted={accepted} "
          f"score={result['final_score']:.12f}",flush=True)
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--registry",default="results/kaggle_baseline/best_registry.json")
    p.add_argument("--n",type=int,default=228)
    p.add_argument("--attempts",type=int,default=24)
    p.add_argument("--iterations",type=int,default=500)
    p.add_argument("--seed",type=int,default=102)
    p.add_argument("--apply",action="store_true")
    p.add_argument("--source-file",help="Certified JSON founder (N-1), e.g. deep N230 best_valid.json")
    p.add_argument("--best-file",help="Write independently certified best N to a new JSON file")
    p.add_argument("--report-every",type=int,default=5)
    p.add_argument("--report",default="results/kaggle_elastic_growth/n228_repair.json")
    p.add_argument("--checkpoint",default="results/kaggle_elastic_growth/n228_nearest.npz")
    a=p.parse_args()
    run(a.registry,n=a.n,attempts=a.attempts,iterations=a.iterations,
        seed=a.seed,apply=a.apply,report=a.report,
        checkpoint=a.checkpoint,report_every=a.report_every,
        source_file=a.source_file,best_file=a.best_file)

if __name__=="__main__": main()
