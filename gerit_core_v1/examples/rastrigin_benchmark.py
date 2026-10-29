"""Rastrigin multimodal benchmark: compare one parent with gradual branching."""
import argparse
import json
import math
import statistics
from pathlib import Path
from gerit_core import Search, Settings


class Rastrigin:
    """2D search domain [-5.12,5.12]^2; global minimum f(0,0)=0."""
    def __init__(self):
        self.basins = {}

    def initial(self, rng):
        return [3.25, -3.75]  # deliberately away from the global optimum

    def feasible(self, state):
        return len(state)==2 and all(math.isfinite(x) and -5.12<=x<=5.12 for x in state)

    def evaluate(self, state):
        x,y=state
        value=20+x*x+y*y-10*(math.cos(2*math.pi*x)+math.cos(2*math.pi*y))
        basin=(round(x),round(y))
        if basin not in self.basins or value<self.basins[basin][0]:
            self.basins[basin]=(value,tuple(state))
        return value

    def distance(self,a,b):
        return math.dist(a,b)

    def encode(self,state):
        return list(state)

    def decode(self,state):
        return list(state)


def local(state,rng,intensity):
    state[rng.randrange(2)]+=rng.gauss(0,0.16*intensity)
    return state


def coordinated(state,rng,intensity):
    return [x+rng.gauss(0,0.18*intensity) for x in state]


def jump(state,rng,intensity):
    return [x+rng.gauss(0,1.0*intensity) for x in state]


def relocation(state,rng,intensity):
    return [rng.uniform(-5.12,5.12),rng.uniform(-5.12,5.12)]


def trial(seed,parents,budget,iterations,folder,interval):
    problem=Rastrigin()
    config=Settings(iterations=iterations,evaluation_budget=budget,
        children_per_parent=10,max_parents=parents,
        population_adjust_interval=interval,history_depth=120,
        branch_seed_attempts=128,absolute_regression=30.,
        min_distance=0.3,seed=seed,output_dir=str(folder))
    result=Search(problem,{'local':local,'coordinated':coordinated,
        'jump':jump,'relocation':relocation},config).run()
    near_centers={str(cell):round(v,6) for cell,(v,p) in problem.basins.items()
                  if math.dist(cell,p)<0.13}
    events={key:sum(event['event']==key for event in result.events)
            for key in ('population_expand','population_contract','population_shortfall')}
    return {'seed':seed,'max_parents':parents,'best':result.best_objective,
        'state':result.best_state,'evaluations':result.evaluations,
        'generations':result.generations,'global_success':result.best_objective<1e-3,
        'visited_basins':len(problem.basins),'near_center_basins':len(near_centers),
        'near_center_values':near_centers,'events':events}


def main():
    parser=argparse.ArgumentParser(description='Gerit multiwell Rastrigin benchmark.')
    parser.add_argument('--seeds',type=int,default=5)
    parser.add_argument('--start-seed',type=int,default=3000)
    parser.add_argument('--evaluation-budget',type=int,default=20000)
    parser.add_argument('--iterations',type=int,default=3000)
    parser.add_argument('--max-parents',type=int,default=5)
    parser.add_argument('--population-adjust-interval',type=int,default=20)
    parser.add_argument('--output-dir',default='results/rastrigin-benchmark')
    args=parser.parse_args()
    if args.seeds<1 or args.max_parents<2:
        parser.error('seeds >= 1 and max-parents >= 2 required')
    out=Path(args.output_dir)
    out.mkdir(parents=True,exist_ok=True)
    runs=[]
    for seed in range(args.start_seed,args.start_seed+args.seeds):
        for label,parents in [('single',1),('adaptive',args.max_parents)]:
            record=trial(seed,parents,args.evaluation_budget,args.iterations,
                         out/label/str(seed),args.population_adjust_interval)
            record['mode']=label
            runs.append(record)
            print('seed={} mode={} best={:.9g} visited={} near_centers={} success={} events={}'.format(
                seed,label,record['best'],record['visited_basins'],
                record['near_center_basins'],record['global_success'],record['events']),flush=True)
    summary={}
    for label in ('single','adaptive'):
        group=[r for r in runs if r['mode']==label]
        summary[label]={'successes':sum(r['global_success'] for r in group),
            'trials':len(group),
            'median_best':statistics.median(r['best'] for r in group),
            'mean_visited_basins':statistics.mean(r['visited_basins'] for r in group)}
    (out/'comparison.json').write_text(json.dumps(
        {'problem':'Rastrigin 2D','global_optimum':0.0,'success_threshold':1e-3,
         'summary':summary,'runs':runs},indent=2),encoding='utf8')
    print('COMPARISON:',json.dumps(summary,indent=2))
    print('output:',out.resolve())


if __name__=='__main__':
    main()
