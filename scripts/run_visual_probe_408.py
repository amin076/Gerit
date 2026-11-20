#!/usr/bin/env python3
"""Gerit visual experiment: 200 reproducible generation snapshots for HTML replay.

This is a standalone experimental search, NOT Gerit's production evolutionary
solver. No registry writes. A frame is the best *complete* packing so far.
"""
import argparse
import json
import math
import random
from pathlib import Path

H = math.sqrt(0.5)


def vertices(q):
    x, y, a = q
    c, s = math.cos(a), math.sin(a)
    return [(x+dx*c-dy*s, y+dx*s+dy*c)
            for dx,dy in ((-.5,-.5),(.5,-.5),(.5,.5),(-.5,.5))]


def overlap(p, q):
    a, b = vertices(p), vertices(q)
    for poly in (a,b):
        for k in (0,1):
            vx = poly[k+1][0]-poly[k][0]
            vy = poly[k+1][1]-poly[k][1]
            ax,ay = -vy,vx
            pa = [x*ax+y*ay for x,y in a]
            pb = [x*ax+y*ay for x,y in b]
            if min(max(pa),max(pb)) <= max(min(pa),min(pb)) + 1e-11:
                return False
    return True


def normalize(items):
    pts = [v for q in items for v in vertices(q)]
    x0,x1 = min(x for x,y in pts),max(x for x,y in pts)
    y0,y1 = min(y for x,y in pts),max(y for x,y in pts)
    return [(x-x0,y-y0,a) for x,y,a in items],max(x1-x0,y1-y0)


def valid(items, side=None):
    pts = [v for q in items for v in vertices(q)]
    if side is not None and (min(x for x,y in pts)<-1e-8
            or min(y for x,y in pts)<-1e-8
            or max(x for x,y in pts)>side+1e-8
            or max(y for x,y in pts)>side+1e-8):
        return False
    for i,p in enumerate(items):
        for q in items[:i]:
            if overlap(p,q):
                return False
    return True


def registry(path,n):
    root=json.loads(path.read_text(encoding='utf-8'))
    p=root['problems'][str(n)]
    items=[(float(s['x']),float(s['y']),float(s.get('angle',0)))
           for s in p['squares']]
    return normalize(items)


def cross(a,b,spacing=1e-5,clearance=1e-4):
    """20x20 rigid unit-square grid, noncentral cross with one 45-degree square."""
    pitch=1+spacing
    gap=H+clearance
    items=[((ix+.5)*pitch+(gap if ix>=a else 0),
            (iy+.5)*pitch+(gap if iy>=b else 0),0.0)
           for ix in range(20) for iy in range(20)]
    items.append((a*pitch+gap/2,b*pitch+gap/2,math.pi/4))
    return normalize(items)


def insertion(items, side, rng, attempts):
    """Try inserting a unit square into free space (no scaling or overlap)."""
    for _ in range(attempts):
        angle=rng.choice((0.,0.,0.,math.pi/4,-math.pi/4))
        h=(abs(math.cos(angle))+abs(math.sin(angle)))/2
        x=rng.uniform(h,side-h)
        y=rng.uniform(h,side-h)
        q=(x,y,angle)
        if all(not overlap(q,p) for p in items):
            return q
    return None


def frame(g,items,side,comment):
    return {'generation':g,'n':len(items),'side':side,
            'note':comment,'squares':[{'x':x,'y':y,'angle_deg':math.degrees(a)}
                                      for x,y,a in items]}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--registry',type=Path,default=Path('results/kaggle_baseline/best_registry.json'))
    ap.add_argument('--n',type=int,default=408)
    ap.add_argument('--generations',type=int,default=200)
    ap.add_argument('--insert-samples',type=int,default=250)
    ap.add_argument('--seed',type=int,default=20261120)
    ap.add_argument('--out',type=Path,default=Path('results/visual_probe_408'))
    args=ap.parse_args()
    if args.generations<1 or args.insert_samples<1:
        ap.error('generations and insert-samples must be positive')
    rng=random.Random(args.seed)
    items,side=registry(args.registry,args.n)
    if len(items)!=args.n or not valid(items,side):
        raise RuntimeError('Invalid baseline packing')
    best, best_side=list(items),side
    frames=[frame(0,best,best_side,'registry baseline')]
    logs=[]
    for g in range(1,args.generations+1):
        # Change the cross location every generation, not only the square center.
        if args.n>=401:
            a,b=rng.randint(1,19),rng.randint(1,19)
            candidate,L=cross(a,b)
            origin=f'cross ({a},{b})'
        else:
            candidate,L=list(items),side
            origin='registry baseline'
        count=0
        while len(candidate)<args.n:
            new=insertion(candidate,L,rng,args.insert_samples)
            if new is None:
                break
            candidate.append(new)
            count+=1
        reached=len(candidate)==args.n
        checked=reached and valid(candidate,L)
        improved=checked and L<best_side-1e-9
        if improved:
            best,best_side=list(candidate),L
        note=f'{origin}: reached {len(candidate)}/{args.n}; added={count}; improvement={improved}'
        frames.append(frame(g,best,best_side,note))
        logs.append({'generation':g,'source':origin,'reached':len(candidate),
                     'added':count,'valid_complete':checked,'improved':improved,
                     'candidate_side':L,'best_side':best_side})
        if g%10==0 or improved:
            print(f'GEN {g}/{args.generations} best_L={best_side:.9f} '
                  f'candidate={len(candidate)}/{args.n} improved={improved}',flush=True)
    args.out.mkdir(parents=True,exist_ok=True)
    payload={'target_n':args.n,'generations':args.generations,'seed':args.seed,
             'frame_delay_ms':500,'baseline_side':side,
             'best_side':best_side,'frames':frames,'log':logs,
             'warning':'Standalone geometry probe, not production Gerit generations. '
                       'Float SAT only; interval certification required before submission.'}
    path=args.out/'history.json'
    path.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(f'WROTE {path} best L={best_side:.9f}',flush=True)


if __name__=='__main__':
    main()
