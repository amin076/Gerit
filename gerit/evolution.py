"""Gerit evolutionary search over strictly validated rigid-square packings."""
from __future__ import annotations
import json, math, random
from dataclasses import asdict, dataclass
from itertools import combinations
from pathlib import Path
from .config import RunConfig
from .geometry import Packing, Square, grid_baseline, minimum_bounding_square, validate_packing

@dataclass(frozen=True)
class Generation:
    generation: int
    evaluations: int
    best_side: float
    population_best: float
    distinct: int
    valid_children: int

@dataclass(frozen=True)
class Result:
    config: RunConfig
    best: Packing
    history: tuple[Generation, ...]
    evaluations: int
    accepted_children: int

    def to_dict(self) -> dict:
        return {
            "status": "completed",
            "config": asdict(self.config),
            "best": {
                "side": self.best.container_side,
                "area": self.best.container_side**2,
                "unused_area": self.best.container_side**2-len(self.best.squares),
                "squares": [asdict(s) for s in self.best.squares],
                "validation": asdict(validate_packing(self.best, tolerance=0.0)),
            },
            "evaluations": self.evaluations,
            "accepted_children": self.accepted_children,
            "history": [asdict(h) for h in self.history],
        }

    def save(self, file: str | Path) -> None:
        path=Path(file)
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(self.to_dict(),indent=2),encoding="utf-8")

def verified(squares: tuple[Square,...]) -> Packing | None:
    """Normalize a complete candidate and refuse numerical penetration."""
    try:
        p=minimum_bounding_square(squares)
        return p if validate_packing(p,tolerance=0.0).valid else None
    except ValueError:
        return None

def packing_distance(a: Packing,b: Packing) -> float:
    """Fast structural proxy; ignores square labels, translation and rigid rotation."""
    if len(a.squares)!=len(b.squares):
        raise ValueError("Square counts must match")
    def signature(p):
        distances=sorted(math.hypot(x.x-y.x,x.y-y.y) for x,y in combinations(p.squares,2))
        angles=[s.angle%(math.pi/2) for s in p.squares]
        variants=[]
        for reference in [0.,*angles]:
            variants.append(sorted(min((z-reference)%(math.pi/2),(reference-z)%(math.pi/2)) for z in angles))
        return distances,min(variants)
    (d1,a1),(d2,a2)=signature(a),signature(b)
    return .7*sum(abs(x-y) for x,y in zip(d1,d2))/max(1,len(d1)) + .3*sum(abs(x-y) for x,y in zip(a1,a2))/max(1,len(a1))

def select(pool: list[Packing],cfg: RunConfig) -> list[Packing]:
    """Fitness elites + farthest-first novelty, then explicit capacity backfill."""
    ordered=sorted(pool,key=lambda p:p.container_side)
    unique=[]
    for p in ordered:
        if not any(abs(p.container_side-q.container_side)<1e-8 and packing_distance(p,q)<1e-7 for q in unique):
            unique.append(p)
    if not unique:
        raise RuntimeError("Selection pool is empty")
    quota=cfg.selection_slots()
    count=min(quota.get("fitness",0),len(unique))
    selected=unique[:count]
    remaining=unique[count:]
    for _ in range(quota.get("diversity",0)):
        if not remaining: break
        i=max(range(len(remaining)),key=lambda i:(min((packing_distance(remaining[i],q) for q in selected),default=0.),-remaining[i].container_side))
        selected.append(remaining.pop(i))
    # If candidate supply is insufficient, repeat existing valid individuals.
    while len(selected)<cfg.next_generation_population:
        selected.append(unique[len(selected)%len(unique)])
    return selected[:cfg.next_generation_population]

def mutate(parent: Packing,rng: random.Random,side_cap: float) -> Packing | None:
    """Propose a simultaneous subset relocation/rotation; reject invalid destination.

    Intermediate placement proposals are not physical trajectories.
    """
    n=len(parent.squares)
    count=min(n,rng.choice((1,1,2,2,3,n)) if n>=3 else 1)
    moving=set(rng.sample(range(n),count))
    values=list(parent.squares)
    for index in sorted(moving):
        old=values[index]
        found=False
        for attempt in range(85):
            angle=old.angle+rng.uniform(-.7,.7) if attempt%4 else rng.uniform(-math.pi/4,math.pi/4)
            if attempt%3:
                x=old.x+rng.gauss(0,.48)
                y=old.y+rng.gauss(0,.48)
            else:
                x=rng.uniform(.5,side_cap-.5)
                y=rng.uniform(.5,side_cap-.5)
            trial=Square(x,y,angle)
            partial=tuple(values[j] for j in range(n) if j not in moving or j<index)
            if verified((*partial,trial)) is not None:
                values[index]=trial
                found=True
                break
        if not found:
            return None
    child=verified(tuple(values))
    if child is None or child.container_side>side_cap+1e-9:
        return None
    return child

def evolve(cfg: RunConfig, *, output_dir: str | None = None, image_columns: int = 5, adaptive: bool = False, coordinated: bool = False, compression: bool = False, learning: bool = False) -> Result:
    """Run a fully audited seeded experiment, retaining every proposal and selection.

    When output_dir is given, emits persistent logs and one population PNG per
    completed generation, including generation zero.
    """
    import time
    from .records import RunRecorder, utc_now
    from .adaptive import AdaptiveController, mutate_adaptive
    from .coordinated import CoordinatedController, mutate_coordinated
    from .local_compression import CompressionSettings, compress_valid
    from .learning import LearningController, propose_learned
    started_at=utc_now()
    clock=time.perf_counter()
    if cfg.initialization_source not in {"grid_mutations","random_valid"}:
        raise NotImplementedError("file/agent initialization adapters are not implemented")
    if cfg.diversity_metric!="center_distances_angles":
        raise ValueError("Unsupported diversity metric")
    if compression and not (coordinated or learning):
        raise ValueError("compression=True requires coordinated=True or learning=True")
    if sum(bool(x) for x in (adaptive,coordinated,learning))>1:
        raise ValueError("adaptive, coordinated and learning are alternative mutators")
    rng=random.Random(cfg.seed)
    adaptive_controller=AdaptiveController() if adaptive else None
    coordinated_controller=CoordinatedController() if coordinated else None
    learning_controller=LearningController() if learning else None
    learning_policies: dict[int,dict]={}
    compression_settings=CompressionSettings()
    compression_trials=0
    compression_moves=0
    def make_child(parent: Packing, parent_id: int | None = None):
        nonlocal compression_trials,compression_moves
        if learning_controller is not None:
            parent_policy=learning_policies.get(parent_id)
            if parent_policy is None:
                parent_policy=learning_controller.new_policy()
            raw,meta=propose_learned(parent,rng,cfg.initial_container_side,
                                     parent_policy,learning_controller)
            child=raw
            improvement_from_compression=0.0
            if raw is not None:
                child,compressed_meta=compress_valid(raw,rng,compression_settings,cfg.initial_container_side)
                compression_trials+=compressed_meta["compression_trials"]
                compression_moves+=compressed_meta["compression_accepted"]
                improvement_from_compression=raw.container_side-child.container_side
                meta["local_compression"]={
                    "compression_trials":compressed_meta["compression_trials"],
                    "compression_accepted":compressed_meta["compression_accepted"],
                    "compression_delta_side":improvement_from_compression,
                }
            inherited,feedback=learning_controller.update(
                parent_policy,meta,child is not None,
                parent.container_side-raw.container_side if raw is not None else 0.0,
                improvement_from_compression,parent.container_side)
            meta["learning_feedback"]=feedback
            return child,meta,inherited
        if coordinated_controller is not None:
            child,meta=mutate_coordinated(parent,rng,cfg.initial_container_side,coordinated_controller)
            if compression and child is not None:
                child,compressed_meta=compress_valid(child,rng,compression_settings,cfg.initial_container_side)
                compression_trials+=compressed_meta["compression_trials"]
                compression_moves+=compressed_meta["compression_accepted"]
                meta["local_compression"]=compressed_meta
            return child,meta,None
        if adaptive_controller is not None:
            child,meta=mutate_adaptive(parent,rng,cfg.initial_container_side,adaptive_controller)
            return child,meta,None
        return mutate(parent,rng,cfg.initial_container_side),None,None
    base=grid_baseline(cfg.n_squares)
    if cfg.initial_container_side+1e-12<base.container_side:
        raise ValueError("Initial container is smaller than grid baseline")
    recorder=RunRecorder(output_dir,{**asdict(cfg),"adaptive_enabled":adaptive,"coordinated_enabled":coordinated,"compression_enabled":(compression or learning),"learning_enabled":learning},image_columns) if output_dir else None
    ids=iter(range(1,2**63))
    parents: list[tuple[int,Packing]]=[]
    evaluations=0
    accepted=0
    rejected=0
    def propose(packing: Packing | None, generation: int, parent_id: int | None,
                origin: str, mutation: dict | None = None,
                policy: dict | None = None) -> tuple[int,Packing] | None:
        nonlocal evaluations, accepted, rejected
        uid=next(ids)
        evaluations+=1
        valid=packing is not None and validate_packing(packing,tolerance=0.0).valid
        if origin!="seed":
            if valid: accepted+=1
            else: rejected+=1
        if valid and learning_controller is not None:
            learning_policies[uid]=policy if policy is not None else learning_controller.new_policy()
        if recorder:
            recorder.append("individuals.jsonl",{
                "individual_id":uid,"generation_created":generation,
                "parent_ids":[] if parent_id is None else [parent_id],
                "origin":origin,"valid":valid,
                "rejected_reason":None if valid else "invalid_or_failed_mutation",
                "container_side":packing.container_side if valid else None,
                "squares":[asdict(s) for s in packing.squares] if valid else None,
                "mutation":mutation,
                "recorded_at":utc_now()
            })
        return (uid,packing) if valid else None
    initial=verified(base.squares)
    assert initial is not None
    seed=propose(initial,0,None,"seed")
    assert seed is not None
    parents=[seed]
    while len(parents)<cfg.initial_population and evaluations<cfg.max_evaluations:
        parent_id,parent=rng.choice(parents) if cfg.initialization_source=="grid_mutations" else parents[0]
        child, mutation_meta, learned_policy=make_child(parent,parent_id)
        item=propose(child,0,parent_id,"initial_mutation",
                     (mutation_meta if (adaptive or coordinated or learning) else ({"changed_indices": [i for i,(x,y) in enumerate(zip(parent.squares,child.squares)) if x!=y]} if child else None)),
                     policy=learned_policy)
        if item: parents.append(item)
    # Duplicated survival slots are deliberate but not new individuals.
    while len(parents)<cfg.initial_population:
        parents.append(parents[0])
    best=min((p for _,p in parents),key=lambda p:p.container_side)
    best_id=min(parents,key=lambda item:item[1].container_side)[0]
    def snapshot(gen:int, children:int):
        unique_ids=len(set(i for i,_ in parents))
        population_best=min(p.container_side for _,p in parents)
        value=Generation(gen,evaluations,best.container_side,population_best,unique_ids,children)
        if recorder:
            recorder.append("generations.jsonl",{
                **asdict(value),"selected_ids":[i for i,_ in parents],
                "best_individual_id":best_id,"timestamp":utc_now(),
                "learning_global_probability":learning_controller.probabilities(learning_controller.new_policy(),learning_controller.context(best)) if learning_controller is not None else None,
                "elapsed_seconds":time.perf_counter()-clock
            })
            recorder.image(gen,parents,cfg.initial_container_side)
        return value
    history=[snapshot(0,0)]
    stop_reason="max_generations"
    for gen in range(1,cfg.max_generations+1):
        if evaluations>=cfg.max_evaluations:
            stop_reason="max_evaluations"
            break
        proposals=[]
        old_parents=list(parents)
        for parent_id,parent in old_parents:
            for _ in range(cfg.offspring_per_parent):
                if evaluations>=cfg.max_evaluations: break
                child, mutation_meta, learned_policy=make_child(parent,parent_id)
                item=propose(child,gen,parent_id,"offspring",
                             (mutation_meta if (adaptive or coordinated or learning) else ({"changed_indices":[i for i,(x,y) in enumerate(zip(parent.squares,child.squares)) if x!=y]} if child else None)),
                             policy=learned_policy)
                if item: proposals.append(item)
            if evaluations>=cfg.max_evaluations: break
        pool=old_parents+proposals
        survivor_packings=select([p for _,p in pool],cfg)
        # Preserve individual identity, even when identical geometries coexist.
        members_by_identity={id(p):(uid,p) for uid,p in pool}
        parents=[members_by_identity[id(p)] for p in survivor_packings]
        if learning_controller is not None:
            live_ids={uid for uid,_ in parents}
            learning_policies={uid:pol for uid,pol in learning_policies.items() if uid in live_ids}
        current_id,current=min(parents,key=lambda item:item[1].container_side)
        if current.container_side<best.container_side:
            best,best_id=current,current_id
        if recorder:
            selected_ids={i for i,_ in parents}
            for uid,p in pool:
                recorder.append("selection.jsonl",{
                    "generation":gen,"individual_id":uid,"selected":uid in selected_ids,
                    "reason":"survived_selection" if uid in selected_ids else "not_selected",
                    "side":p.container_side
                })
        history.append(snapshot(gen,len(proposals)))
        if evaluations>=cfg.max_evaluations:
            stop_reason="max_evaluations"
            break
    assert validate_packing(best,tolerance=0.0).valid
    assert all(y.best_side<=x.best_side+1e-12 for x,y in zip(history,history[1:]))
    result=Result(cfg,best,tuple(history),evaluations,accepted)
    if recorder:
        recorder.write("run_summary.json",{
            "started_at":started_at,"finished_at":utc_now(),
            "elapsed_seconds":time.perf_counter()-clock,
            "completed_generations":len(history)-1,
            "population_snapshots":len(history),
            "population_images":len(history),
            "evaluations":evaluations,"accepted_children":accepted,
            "rejected_children":rejected,"stop_reason":stop_reason,
            "best_side":best.container_side,"best_individual_id":best_id,
            "best_validation":asdict(validate_packing(best,tolerance=0.0)),
            "adaptive_enabled":adaptive,
            "adaptive_controller":adaptive_controller.snapshot() if adaptive_controller is not None else None,
            "coordinated_enabled":coordinated,
            "coordinated_controller":coordinated_controller.snapshot() if coordinated_controller is not None else None,
            "learning_enabled":learning,
            "learning_controller":learning_controller.snapshot() if learning_controller is not None else None,
            "compression_enabled":(compression or learning),
            "compression_trials":compression_trials,
            "compression_accepted_moves":compression_moves
        })
        if learning_controller is not None:
            recorder.write("selected_population_final.json",{
                "generation":len(history)-1,
                "selected_members":[{
                    "individual_id":uid,"container_side":p.container_side,
                    "squares":[asdict(sq) for sq in p.squares],
                    "policy":learning_policies[uid],
                } for uid,p in parents],
                "global_learning_policy":learning_controller.global_policy,
            })
        result.save(recorder.directory/"best_result.json")
    return result
