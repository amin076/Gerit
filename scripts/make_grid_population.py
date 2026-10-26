"""Create an explicit grid-baseline experiment input (not evolutionary discovery)."""
from __future__ import annotations
import argparse,json,sys
from dataclasses import asdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from gerit.grid_bounds import checked_grid,grid_bounds
from gerit.learning import LearningController


def build_grid_input(n:int, population:int=20):
    if type(population) is not int or population < 1:
        raise ValueError('population must be positive')
    layout=checked_grid(n)
    controller=LearningController()
    members=[{'individual_id':i+1,'container_side':layout.container_side,
              'squares':[asdict(s) for s in layout.squares],
              'policy':controller.new_policy()} for i in range(population)]
    return {'generation':0,'selected_members':members,'global_policy':controller.new_policy(),
            'initialization_kind':'explicit_known_grid_baseline',
            'baseline':grid_bounds(n).to_dict(),
            'note':'All initial genomes are copies of a known grid. This is a control, not a found result.'}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--squares',type=int,required=True)
    ap.add_argument('--population',type=int,default=20)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    result=build_grid_input(args.squares,args.population)
    output=args.output.expanduser().resolve()
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as f:
        json.dump(result,f,indent=2)
    b=result['baseline']
    print(f"Grid baseline: n={b['squares']}, L={b['grid_upper_side']}, "
          f"rows={b['grid_rows']}, cols={b['grid_columns']}; saved {output}")

if __name__=='__main__':main()