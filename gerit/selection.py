"""Existing Gerit fitness+diversity selection, intentionally unchanged."""
import math
from itertools import combinations
from .geometry import Packing

def packing_distance(a: Packing,b: Packing)->float:
    if len(a.squares)!=len(b.squares):raise ValueError('Square counts must match')
    def signature(p):
        distances=sorted(math.hypot(x.x-y.x,x.y-y.y) for x,y in combinations(p.squares,2))
        angles=[s.angle%(math.pi/2) for s in p.squares]
        variants=[]
        for reference in [0.,*angles]:
            variants.append(sorted(min((z-reference)%(math.pi/2),(reference-z)%(math.pi/2)) for z in angles))
        return distances,min(variants)
    (d1,a1),(d2,a2)=signature(a),signature(b)
    return .7*sum(abs(x-y) for x,y in zip(d1,d2))/max(1,len(d1))+.3*sum(abs(x-y) for x,y in zip(a1,a2))/max(1,len(a1))

def select(pool:list[Packing],n:int=20,fitness_share:float=.75)->list[Packing]:
    ordered=sorted(pool,key=lambda p:p.container_side)
    unique=[]
    for p in ordered:
        if not any(abs(p.container_side-q.container_side)<1e-8 and packing_distance(p,q)<1e-7 for q in unique):
            unique.append(p)
    if not unique:raise RuntimeError('Selection pool is empty')
    # same Hamilton allocation for two groups (n=20 => 15 fitness / 5 diversity)
    fitness_slots=round(n*fitness_share)
    count=min(fitness_slots,len(unique))
    selected=unique[:count]
    remaining=unique[count:]
    for _ in range(n-fitness_slots):
        if not remaining:break
        i=max(range(len(remaining)),key=lambda i:(min((packing_distance(remaining[i],q) for q in selected),default=0.),-remaining[i].container_side))
        selected.append(remaining.pop(i))
    while len(selected)<n:
        selected.append(unique[len(selected)%len(unique)])
    return selected[:n]