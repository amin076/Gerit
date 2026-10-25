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

def evolve(cfg: RunConfig) -> Result:
    """A bounded, seeded (mu+lambda) evolutionary packing search.

    No claim of global optimality. Unimplemented external population sources fail
    explicitly instead of silently generating substitute populations.
    """
    if cfg.initialization_source not in {"grid_mutations","random_valid"}:
        raise NotImplementedError("file/agent initialization adapters are not implemented")
    if cfg.diversity_metric!="center_distances_angles":
        raise ValueError("Unsupported diversity metric")
    rng=random.Random(cfg.seed)
    base=grid_baseline(cfg.n_squares)
    if cfg.initial_container_side+1e-12<base.container_side:
        raise ValueError("Initial container is smaller than grid baseline")
    baseline=verified(base.squares)
    assert baseline is not None
    population=[baseline]
    evaluations=1
    while len(population)<cfg.initial_population and evaluations<cfg.max_evaluations:
        parent=rng.choice(population) if cfg.initialization_source=="grid_mutations" else baseline
        child=mutate(parent,rng,cfg.initial_container_side)
        evaluations+=1
        if child is not None: population.append(child)
    while len(population)<cfg.initial_population:
        population.append(baseline)
    best=min(population,key=lambda p:p.container_side)
    history=[Generation(0,evaluations,best.container_side,best.container_side,len({tuple((s.x,s.y,s.angle) for s in p.squares) for p in population}),0)]
    accepted=0
    for g in range(1,cfg.max_generations+1):
        if evaluations>=cfg.max_evaluations: break
        children=[]
        for parent in population:
            for _ in range(cfg.offspring_per_parent):
                if evaluations>=cfg.max_evaluations: break
                child=mutate(parent,rng,cfg.initial_container_side)
                evaluations+=1
                if child is not None: children.append(child)
            if evaluations>=cfg.max_evaluations: break
        accepted+=len(children)
        population=select(population+children,cfg)
        current=min(population,key=lambda p:p.container_side)
        if current.container_side<best.container_side: best=current
        history.append(Generation(g,evaluations,best.container_side,current.container_side,len({tuple((s.x,s.y,s.angle) for s in p.squares) for p in population}),len(children)))
    assert validate_packing(best,tolerance=0.0).valid
    assert all(y.best_side<=x.best_side+1e-12 for x,y in zip(history,history[1:]))
    return Result(cfg,best,tuple(history),evaluations,accepted)
