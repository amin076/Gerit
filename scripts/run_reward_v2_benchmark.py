"""Matched validation-call budget, paired-seed 12-square credit assignment study.

The common proposal mechanism is identical in all three arms. Only policy
updates differ: version-1 credit, cost-aware version-2 credit, or frozen.
Mutation and compression checks are counted by instrumenting the exact two
geometric validator call sites used by both operations.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,random,statistics,time,zipfile,sys,shutil
from dataclasses import asdict
from pathlib import Path
from collections import Counter

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.path.insert(0,str(Path(__file__).resolve().parent))
from gerit import learning as learning_mod, local_compression as compression_mod
from gerit.geometry import Square,Packing,validate_packing,square_vertices
from gerit.selection import select
from gerit.learning import LearningController, propose_learned
from gerit.reward_v2 import CreditController
from gerit.local_compression import CompressionSettings, compress_valid
from run_learning_pilot import draw_mosaic,draw_best

ROOT=Path('/mnt/data/Gerit_reward_v2_benchmark')
SOURCE_ZIP=Path('/mnt/data/Gerit_round13_12squares_100_generations.zip')
SEEDS=(2601,2602,2603)
ARMS=('v2_credit','frozen','v1_credit')
CAP=30000
N=100

class BudgetReached(Exception):
    pass

class GeometryBudget:
    def __init__(self,limit):
        self.limit=limit
        self.used=0
        self.raw=0
        self.comp=0
        self.phase='raw'
        self.old_learning=None
        self.old_compression=None
    def check(self,*args,**kwargs):
        if self.used>=self.limit:
            raise BudgetReached()
        self.used+=1
        if self.phase=='raw':self.raw+=1
        else:self.comp+=1
        return self.orig(*args,**kwargs)
    def __enter__(self):
        self.orig=learning_mod.validate_packing
        self.old_learning=learning_mod.validate_packing
        self.old_compression=compression_mod.validate_packing
        learning_mod.validate_packing=self.check
        compression_mod.validate_packing=self.check
        return self
    def __exit__(self,*exc):
        learning_mod.validate_packing=self.old_learning
        compression_mod.validate_packing=self.old_compression

def read_source():
    with zipfile.ZipFile(SOURCE_ZIP) as z:
        hits=[p for p in z.namelist() if p.endswith('/selected_population_final.json')]
        if len(hits)!=1:raise ValueError('Incorrect initial population archive')
        raw=z.read(hits[0]); data=json.loads(raw)
    members=data['selected_members']
    if len(members)!=N:raise ValueError('Expected 100 parents')
    pop=[]
    for m in members:
        p=Packing(tuple(Square(**s) for s in m['squares']),float(m['container_side']))
        assert len(p.squares)==12 and validate_packing(p,tolerance=0.0).valid
        pop.append((int(m['individual_id']),p))
    if len({id for id,p in pop})!=N:raise ValueError('Duplicate identifiers')
    return pop, hashlib.sha256(raw).hexdigest()

def record(f,obj):
    f.write(json.dumps(obj,ensure_ascii=False,separators=(',',':'))+'\n')

def run_arm(seed,arm,source,source_sha,budget):
    dest=ROOT/f'seed_{seed}'/arm
    dest.mkdir(parents=True,exist_ok=True)
    genf=(dest/'generations.jsonl').open('w',encoding='utf-8')
    indf=(dest/'individuals.jsonl').open('w',encoding='utf-8')
    selfile=(dest/'selection.jsonl').open('w',encoding='utf-8')
    population=list(source)
    byid={uid:CreditController().new_policy() for uid,p in population} # all same fresh policies
    controller=CreditController() if arm in ('v2_credit','frozen') else LearningController()
    rng=random.Random(seed)
    comp_settings=CompressionSettings()
    next_id=max(uid for uid,p in population)+1
    best_id,best=min(population,key=lambda x:x[1].container_side)
    start_side=best.container_side
    raw_valid=final_valid=raw_improvements=final_improvements=0
    raw_checks_total=comp_checks_total=0
    births=0; completed_generations=0
    comp_positive=0; comp_gain_sum=0.0; raw_gain_positive_sum=0.0
    history=[]; action_summary=Counter()
    start=time.perf_counter()
    def snapshot(g,completed:bool):
        row={'generation':g,'complete_generation':completed,
             'best_side':best.container_side,'best_id':best_id,'population_best':min(p.container_side for uid,p in population),
             'distinct_ids':len({uid for uid,p in population}),
             'selected_ids':[uid for uid,p in population],
             'geometry_checks':gate.used,'raw_geometry_checks':gate.raw,'compression_geometry_checks':gate.comp,
             'complete_births':births,'raw_valid':raw_valid,'valid_children':final_valid,
             'raw_improvements':raw_improvements,'final_improvements':final_improvements,
             'elapsed_seconds':time.perf_counter()-start}
        history.append(row);record(genf,row);genf.flush()
    for uid,p in population:
        record(indf,{'id':uid,'generation':0,'parent_ids':[],'valid':True,'origin':'imported_round13',
                     'L':p.container_side,'squares':[asdict(s) for s in p.squares]})
    draw_mosaic(dest/'start.png',population)
    try:
        with GeometryBudget(budget) as gate:
            snapshot(0,True)
            while gate.used<budget:
                g=completed_generations+1
                old=list(population);children=[]
                partial=False
                for parent_uid,parent in old:
                    if gate.used>=budget:
                        partial=True;break
                    parent_policy=byid[parent_uid]
                    before_raw=gate.raw
                    before_comp=gate.comp
                    try:
                        gate.phase='raw'
                        raw,meta=propose_learned(parent,rng,5.0,parent_policy,controller)
                        used_raw=gate.raw-before_raw
                        comp_gain=0.0
                        child=raw
                        if raw is not None:
                            gate.phase='comp'
                            child,compression_meta=compress_valid(raw,rng,comp_settings,5.0)
                            comp_gain=raw.container_side-child.container_side
                        used_comp=gate.comp-before_comp
                    except BudgetReached:
                        partial=True
                        break
                    births+=1
                    valid=child is not None and validate_packing(child,tolerance=0.0).valid
                    if valid:
                        final_valid+=1
                        children.append((next_id,child))
                    if raw is not None:raw_valid+=1
                    raw_gain=parent.container_side-raw.container_side if raw is not None else 0.0
                    final_gain=parent.container_side-child.container_side if valid else 0.0
                    if valid and raw_gain>1e-8:
                        raw_improvements+=1;raw_gain_positive_sum+=raw_gain
                    if valid and final_gain>1e-8:final_improvements+=1
                    if valid and comp_gain>1e-8:
                        comp_positive+=1;comp_gain_sum+=comp_gain
                    if arm=='v2_credit':
                        child_policy,feedback=controller.update(parent_policy,meta,valid,raw_gain,comp_gain,
                            parent.container_side,used_raw,used_comp,train=True)
                    elif arm=='frozen':
                        child_policy,feedback=controller.update(parent_policy,meta,valid,raw_gain,comp_gain,
                            parent.container_side,used_raw,used_comp,train=False)
                    else:
                        child_policy,feedback=controller.update(parent_policy,meta,valid,raw_gain,comp_gain,parent.container_side)
                        feedback.update({'raw_geometry_checks':used_raw,'compression_geometry_checks':used_comp,
                                         'total_geometry_checks':used_raw+used_comp})
                    if valid:byid[next_id]=child_policy
                    action_summary[meta['action']]+=1
                    record(indf,{'id':next_id,'generation':g,'parent_ids':[parent_uid],
                                 'valid':valid,'L':child.container_side if valid else None,
                                 'squares':[asdict(s) for s in child.squares] if valid else None,
                                 'mutation':meta,'feedback':feedback})
                    next_id+=1
                pool=old+children
                winners=select([p for uid,p in pool],n=N,fitness_share=.90)
                uid_index={id(p):uid for uid,p in pool}
                population=[(uid_index[id(p)],p) for p in winners]
                survivors={uid for uid,p in population}
                for uid,p in pool:
                    record(selfile,{'generation':g,'id':uid,'selected':uid in survivors,'L':p.container_side})
                byid={uid:byid[uid] for uid in survivors}
                cid,cbest=min(population,key=lambda x:x[1].container_side)
                if cbest.container_side<best.container_side:
                    best_id,best=cid,cbest
                if partial:
                    snapshot(g,False)
                    break
                else:
                    completed_generations+=1
                    snapshot(g,True)
                if completed_generations>100:raise RuntimeError('Safety limit for generations exceeded')
    finally:
        indf.close();genf.close();selfile.close()
    assert gate.used==budget, (arm,seed,gate.used,budget)
    assert gate.raw+gate.comp==budget
    assert len(population)==N
    assert validate_packing(best,tolerance=0.0).valid
    # Separate independent Shapely check of final 12 rigid squares.
    try:
        from shapely.geometry import Polygon
        polys=[Polygon(square_vertices(s)) for s in best.squares]
        max_overlap=max(polys[i].intersection(polys[j]).area for i in range(12) for j in range(i+1,12))
    except ImportError:
        max_overlap=None
    summary={
        'seed':seed,'arm':arm,'source_sha256':source_sha,'n_squares':12,'population':N,
        'fitness_slots':90,'diversity_slots':10,
        'budget_metric':'strict count of geometric validate_packing calls inside proposal and local compressor',
        'validation_budget':budget,'validation_checks_used':gate.used,
        'raw_geometry_checks':gate.raw,'compression_geometry_checks':gate.comp,
        'births_completed':births,'valid_children':final_valid,'invalid_children':births-final_valid,
        'raw_improving_births':raw_improvements,'final_improving_births':final_improvements,
        'children_compressed':comp_positive,'total_raw_positive_gain':raw_gain_positive_sum,
        'total_child_compression_gain':comp_gain_sum,
        'initial_best_side':start_side,'final_best_side':best.container_side,
        'best_improvement':start_side-best.container_side,
        'best_id':best_id,'full_generations':completed_generations,
        'partial_generation':len(history)-1 if history[-1]['complete_generation'] is False else None,
        'shapely_max_overlap_area':max_overlap,
        'wall_seconds':time.perf_counter()-start,
        'action_proposals':dict(action_summary),
        'learning_statistics':controller.snapshot(),
    }
    (dest/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    (dest/'selected_population_final.json').write_text(json.dumps({'generation':len(history)-1,
                'selected_members':[{'individual_id':uid,'container_side':p.container_side,
                    'squares':[asdict(s) for s in p.squares],'policy':byid[uid]} for uid,p in population],
                'global_policy':controller.global_policy},indent=2),encoding='utf-8')
    (dest/'best_result.json').write_text(json.dumps({'individual_id':best_id,'side':best.container_side,
                          'squares':[asdict(s) for s in best.squares]},indent=2),encoding='utf-8')
    draw_mosaic(dest/'final.png',population)
    draw_best(dest/'best.png',best)
    return summary,history

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--budget',type=int,default=CAP)
    args=parser.parse_args()
    if args.budget<1000:raise ValueError('Budget too small')
    if ROOT.exists():shutil.rmtree(ROOT)
    ROOT.mkdir()
    initial,source_sha=read_source()
    (ROOT/'initial_population.json').write_text(json.dumps({'selected_members':[
        {'individual_id':uid,'container_side':p.container_side,'squares':[asdict(s) for s in p.squares]}
        for uid,p in initial]},indent=2),encoding='utf-8')
    results=[]; histories={}
    for seed in SEEDS:
        for arm in ARMS:
            summary,hist=run_arm(seed,arm,initial,source_sha,args.budget)
            results.append(summary);histories[(seed,arm)]=hist
            print(f'seed={seed} arm={arm} checks={summary["validation_checks_used"]} births={summary["births_completed"]} best={summary["final_best_side"]:.9f} gain={summary["best_improvement"]:.9f} runtime={summary["wall_seconds"]:.1f}s',flush=True)
    import numpy as np
    fig,axes=plt.subplots(1,3,figsize=(13,4.2),sharey=True)
    for ax,seed in zip(axes,SEEDS):
        for arm in ARMS:
            rows=histories[(seed,arm)]
            ax.plot([r['geometry_checks'] for r in rows],[r['best_side'] for r in rows],label=arm)
        ax.set_title(f'Seed {seed}');ax.set_xlabel('Geometry validation calls');ax.grid(alpha=.2)
    axes[0].set_ylabel('Best enclosing side L')
    axes[-1].legend(fontsize=8)
    fig.suptitle('12 squares: three mutation-policy strategies, exactly matched geometric-check budgets')
    fig.tight_layout();fig.savefig(ROOT/'comparison.png',dpi=175);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8.8,4.6))
    labels=['v2_credit','frozen','v1_credit']
    means=[statistics.mean(s['final_best_side'] for s in results if s['arm']==name) for name in labels]
    ax.bar(labels,means)
    for i,name in enumerate(labels):
        vals=[s['final_best_side'] for s in results if s['arm']==name]
        for j,y in enumerate(vals):ax.scatter(i+(j-1)*.07,y,color='black',s=25)
    ax.set(ylabel='Best L at cost budget',title='Final best side across three fixed seeds; smaller is better')
    ax.set_ylim(min(means)-.1,max(means)+.1)
    fig.tight_layout();fig.savefig(ROOT/'summary.png',dpi=170);plt.close(fig)
    aggregates={arm:{
        'mean_final_side':statistics.mean(s['final_best_side'] for s in results if s['arm']==arm),
        'median_final_side':statistics.median(s['final_best_side'] for s in results if s['arm']==arm),
        'mean_gain':statistics.mean(s['best_improvement'] for s in results if s['arm']==arm),
        'mean_births':statistics.mean(s['births_completed'] for s in results if s['arm']==arm),
        'mean_valid_children':statistics.mean(s['valid_children'] for s in results if s['arm']==arm),
        'mean_wall_seconds':statistics.mean(s['wall_seconds'] for s in results if s['arm']==arm),
    } for arm in ARMS}
    differences={str(seed):{
        'v2_minus_frozen':next(s['final_best_side'] for s in results if s['seed']==seed and s['arm']=='v2_credit')-next(s['final_best_side'] for s in results if s['seed']==seed and s['arm']=='frozen'),
        'v2_minus_v1':next(s['final_best_side'] for s in results if s['seed']==seed and s['arm']=='v2_credit')-next(s['final_best_side'] for s in results if s['seed']==seed and s['arm']=='v1_credit'),
    } for seed in SEEDS}
    report={'source_population_sha256':source_sha,'seeds':list(SEEDS),'arms':list(ARMS),
            'budget_per_seed_arm':args.budget,'fairness':'all arms have exactly the same number of internal geometric validation calls',
            'differences':differences,'aggregate':aggregates,'runs':results,
            'limitations':'Counts validate_packing invocations, NOT per-axis SAT projections, vertex construction, or runtime. Three paired seeds are exploratory, not statistically conclusive. One proposed child may be aborted at budget boundary.'}
    (ROOT/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    with (ROOT/'comparison.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['seed','arm','validation_checks_used','raw_geometry_checks','compression_geometry_checks','births_completed','valid_children','raw_improving_births','final_improving_births','children_compressed','initial_best_side','final_best_side','best_improvement','full_generations','wall_seconds'])
        writer.writeheader()
        for s in results:writer.writerow({key:s.get(key) for key in writer.fieldnames})
    (ROOT/'README.md').write_text('''# Gerit v2 cost-aware learning benchmark: 12 squares

Nine actual experiments: three matched seeds × (cost-aware learned policy,
frozen uniform policy with identical movement operators, original learned
credit). All start with the 100 selected individuals of the genuine round-13
final population. 90 fitness + 10 diversity selection, 12 rigid unit squares,
side cap 5, exact numerical SAT feasibility, and same local compressor.

Each arm is strictly interrupted at exactly the SAME TOTAL NUMBER of
`validate_packing` calls in mutation plus compression. Proposal counts and
walltimes differ because they are *outcomes* of the algorithms.

v2 independently records child-vs-parent raw mutation gain, compressor-only
gain, and validations spent on mutation/compression. Compression does not get
full mutation credit, and unchanged yet valid children do not receive success
credit. The frozen control uses the identical proposal and compressor but
keeps its probability genes at zero/uniform. v1 is the previous reward.

Notes: validation invocations are a consistent geometry-work proxy, not exact
CPU-time equivalence or a count of SAT projection operations. Comparisons are
paired by initial states and seeds, but random streams diverge after policies
become different. Three seeds do not yield strong statistical proof.

`run_reward_v2_benchmark.py` is the reproduction driver; change absolute
paths near top to relocate. `source_code/` contains every module used.
''',encoding='utf-8')
    source_dir=ROOT/'source_code'
    source_dir.mkdir()
    for p in (Path(__file__), Path(__file__).parent/'gerit/learning.py',Path(__file__).parent/'gerit/reward_v2.py',Path(__file__).parent/'gerit/geometry.py',Path(__file__).parent/'gerit/selection.py',Path(__file__).parent/'gerit/local_compression.py',Path(__file__).parent/'tests/test_reward_v2.py'):
        shutil.copy2(p,source_dir/p.name)
    target=Path('/mnt/data/Gerit_reward_v2_12squares_matched_budget.zip')
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in ROOT.rglob('*'):
            if p.is_file():z.write(p,p.relative_to(ROOT.parent))
    print(json.dumps({'status':'completed','archive':str(target),'aggregates':aggregates,'differences':differences},indent=2),flush=True)

if __name__=='__main__':main()