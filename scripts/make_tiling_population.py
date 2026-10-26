"""Construct explicit connected axis-aligned tiling baselines for any n.

These are known feasible solutions, NOT discovered by the evolving algorithm.
"""
from __future__ import annotations
import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from gerit.connected_tilings import choose_tilings
from gerit.grid_bounds import grid_bounds
from gerit.learning import LearningController


def build_tiling_input(n: int, population: int=20, extra_side: int=0, seed: int=0):
    if not (1 <= population <= 100):
        raise ValueError('population must be 1..100')
    variants=choose_tilings(n,population,max_extra_side=extra_side,seed=seed)
    base=LearningController().new_policy()
    members=[]
    for i in range(population):
        tiling=variants[i % len(variants)]
        members.append({'individual_id':i+1,
                        'container_side':tiling.packing.container_side,
                        'squares':[asdict(s) for s in tiling.packing.squares],
                        'policy':base,
                        'constructive_ancestor':True,
                        'constructive_seed':tiling.metadata()})
    return {'generation':0,'selected_members':members,
            'global_policy':base,
            'known_grid_injected':True,
            'initialization_kind':'explicit_connected_tiling_library',
            'number_distinct_shapes':len(variants),
            'baseline':grid_bounds(n).to_dict(),
            'note':'Known fully-connected unit-grid placements. None is an evolutionary discovery.'}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--squares',type=int,required=True)
    p.add_argument('--population',type=int,default=20)
    p.add_argument('--extra-side',type=int,default=0)
    p.add_argument('--seed',type=int,default=0)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    d=build_tiling_input(a.squares,a.population,a.extra_side,a.seed)
    target=a.output.expanduser().resolve()
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x',encoding='utf-8') as f:
        json.dump(d,f,indent=2)
    print(f'Constructive tiling library n={a.squares}, k={d["baseline"]["grid_upper_side"]}, '
          f'shapes={d["number_distinct_shapes"]} members={a.population} stored={target}')

if __name__=='__main__':main()