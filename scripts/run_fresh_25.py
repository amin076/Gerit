"""Gerit clean-room experimental restart: no previous population or learned weights.

25 parents by default; 12 unit squares; 300 generations; 5 births/parent.
Multiple constructive and stochastic initializers compete in ONE population.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
import random
import shutil
import sys
import time
import zipfile
from collections import Counter
from dataclasses import asdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from gerit.fresh_population import make_fresh_population
from gerit.geometry import Packing, Square, validate_packing
from gerit.selection import packing_distance
from gerit.adaptive_v4 import (AdaptiveCreditController,
    ProgressAwareStagnationController, StagnationSettings, WindowSettings,
    propose_micro, propose_reconfigure)
from gerit.learning import propose_learned
from gerit.local_compression import CompressionSettings, compress_valid
from gerit.visualization import draw_population, draw_best
from gerit.grid_bounds import grid_bounds,automatic_search_cap
from scripts.run_adaptive_tilings import GeometryCounter, geometry_check_shapely, append_jsonl

MODE_NAMES=('normal','precision','escape','diversify')


def relative_angle_spread(packing: Packing) -> float:
    """Largest relative square orientation mod pi/2 (global-rotation invariant)."""
    angles=[s.angle for s in packing.squares]
    period=math.pi/2
    return max((abs((a-b+period/2)%period-period/2)
                for i,a in enumerate(angles) for b in angles[i+1:]),
               default=0.0)


def _is_duplicate(a:Packing,b:Packing)->bool:
    return abs(a.container_side-b.container_side)<1e-8 and packing_distance(a,b)<1e-7


def select_competitive_diverse(pool:list[tuple[int,Packing]], number:int,
                               mode:str)->list[tuple[int,Packing]]:
    """Unlabelled competition: quality, near-best novelty, broad novelty.

    No preference by seed origin or ancestry. Fast deterministic farthest-first
    selection with graded side penalty rather than unconstrained diversity.
    """
    if mode not in MODE_NAMES: raise ValueError(f'Unknown mode {mode}')
    ordered=sorted(pool,key=lambda item:(item[1].container_side,item[0]))
    unique=[]
    equivalent=[]
    for entry in ordered:
        if any(_is_duplicate(entry[1],e[1]) for e in unique):
            equivalent.append(entry)
        else:
            unique.append(entry)
    if not unique:raise ValueError('Cannot select from empty candidate pool')
    # 25 => 16/7/2 in normal; 13/9/3 in deep exploration.
    quality_n=round(number*(.52 if mode=='diversify' else .64))
    frontier_n=round(number*(.12 if mode=='diversify' else .08))
    near_n=number-quality_n-frontier_n
    chosen=unique[:quality_n]
    remain=unique[quality_n:]
    best_L=unique[0][1].container_side
    def take_one(explore:bool):
        if not remain:return False
        # Encourage novelty, but prevent all diversity slots being wasted on
        # needlessly huge squares (the failure seen in Round 22).
        candidate_ids=list(range(len(remain)))
        if not explore:
            restricted=[i for i in candidate_ids if remain[i][1].container_side<=best_L+0.55]
            if restricted:candidate_ids=restricted
        penalty=.06 if explore else .55
        def score(i):
            uid,packing=remain[i]
            novelty=min((packing_distance(packing,x[1]) for x in chosen), default=0.0)
            return (novelty-penalty*max(0.0,packing.container_side-best_L),
                    -packing.container_side,-uid)
        idx=max(candidate_ids,key=score)
        chosen.append(remain.pop(idx));return True
    for _ in range(near_n):
        if not take_one(False):break
    for _ in range(frontier_n):
        if not take_one(True):break
    # If novelty ran out, use remaining actual distinct individuals first.
    for entry in (*remain,*equivalent):
        if len(chosen)>=number:break
        chosen.append(entry)
    while len(chosen)<number:
        chosen.append(unique[len(chosen)%len(unique)])
    return chosen[:number]


def _progress(path:Path,history:list[dict],reference:float)->None:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(9,4.7))
    ax.plot([r['generation'] for r in history],[r['best_side'] for r in history],label='Best discovered or constructed')
    ax.axhline(reference,ls='--',lw=1,label=f'Known grid L={reference:g}')
    ax.set(xlabel='Generation',ylabel='Containing side L',title='Gerit — fresh start (no prior weights or genomes)')
    ax.grid(alpha=.18);ax.legend();fig.tight_layout();fig.savefig(path,dpi=150);plt.close(fig)


def verify_run(directory:Path,summary:dict)->dict:
    def lines(name):
        with (directory/name).open(encoding='utf-8') as f:
            return [json.loads(line) for line in f if line.strip()]
    history=lines('generations.jsonl')
    individuals=lines('individuals.jsonl')
    selection=lines('selection.jsonl')
    final=json.loads((directory/'selected_population_final.json').read_text(encoding='utf-8'))
    n=summary['population'];g=summary['generations']
    assert len(history)==g+1 and len(individuals)==n+summary['proposals']
    assert len(final['selected_members'])==n
    assert len(selection)==g*n+summary['valid_children']
    assert [x['generation'] for x in history]==list(range(g+1))
    assert all(len(x['selected_ids'])==n for x in history)
    assert len(list((directory/'generation_images').glob('gen_*.png')))==g+1
    assert sum(summary['mode_proposals'].values())==summary['proposals']
    assert sum(summary['mode_valid_children'].values())==summary['valid_children']
    assert sum(summary['mode_generations'].values())==g
    assert sum(summary['mode_geometry_checks'].values())==summary['total_geometry_checks']
    ids={x['individual_id'] for x in individuals}
    assert len(ids)==len(individuals)
    for row in individuals:
        if row['generation']>0:
            assert len(row['parent_ids'])==1 and row['parent_ids'][0] in ids
            assert row['parent_ids'][0]<row['individual_id']
        if row['valid']:
            p=Packing(tuple(Square(**s) for s in row['squares']),row['side'])
            assert validate_packing(p,tolerance=0.0).valid
    assert all(b['best_side']<=a['best_side']+1e-12 for a,b in zip(history,history[1:]))
    assert summary['final_selected_max_positive_overlap_area']<=1e-12
    assert summary['final_selected_max_outside_area']<=1e-12
    return {'status':'verified','generations':g,'individuals':len(individuals),
            'selection_records':len(selection),'images':g+1,'survivors':n,
            'max_intersection_area':summary['final_selected_max_positive_overlap_area'],
            'max_outside_area':summary['final_selected_max_outside_area']}


def run(*,squares:int=12,population:int=25,generations:int=300,
        seed:int=2715,directory:Path|str='results/fresh12-p25-g300',
        structural_seeds:int=7,offspring_per_parent:int=5,
        cap_margin:float=.15,make_zip:bool=True,
        stagnation_settings:StagnationSettings|None=None,
        window_settings:WindowSettings|None=None)->dict:
    if type(generations) is not int or generations<1:raise ValueError('generations must be >=1')
    if type(offspring_per_parent) is not int or offspring_per_parent<1:raise ValueError('offspring_per_parent must be >=1')
    if not math.isfinite(cap_margin) or cap_margin<0:raise ValueError('cap_margin must be finite and nonnegative')
    directory=Path(directory).expanduser().resolve()
    if directory.exists():raise FileExistsError(f'Output directory exists: {directory}. Choose a NEW --output-dir')
    # Generate and fully validate BEFORE allocating output directories.
    initial=make_fresh_population(squares,population,structural_seeds,seed)
    initial_kind={i+1:m.source for i,m in enumerate(initial)}
    ancestry=dict(initial_kind)  # diagnostics only: NEVER used by selection
    pop=[(i+1,m.packing) for i,m in enumerate(initial)]
    grid=grid_bounds(squares)
    best_id,best=min(pop,key=lambda pair:(pair[1].container_side,pair[0]))
    best_initial=best.container_side
    focused_cap=automatic_search_cap([best_initial],squares,cap_margin)
    controller=AdaptiveCreditController()  # ZERO trained history; no global_policy imported
    weights={uid:controller.new_policy() for uid,_ in pop}
    stagnation=ProgressAwareStagnationController(best_initial,stagnation_settings,window_settings)
    compressor=CompressionSettings()
    rng=random.Random(seed+7919)
    next_id=population+1
    modes=Counter();stats=Counter();action_counts=Counter();mode_births=Counter();mode_valid=Counter()
    mode_checks=Counter();mode_record_events=Counter();mode_record_gain=Counter()
    initial_origin_breakdown=dict(Counter(initial_kind.values()))
    stochastic_initial_sides=[p.container_side for uid,p in pop
                              if initial_kind[uid]!='connected_tiling']
    competitive_stochastic_initial_count=sum(L<=grid.grid_upper_side+0.4
                                               for L in stochastic_initial_sides)
    initial_relative_orientation_count=sum(relative_angle_spread(p)>0.01
                                           for uid,p in pop)
    initial_metadata=[{'individual_id':uid,'source':initial_kind[uid],
                       'container_side':p.container_side,'squares':[asdict(x) for x in p.squares]}
                      for uid,p in pop]
    directory.mkdir(parents=True)
    images=directory/'generation_images';images.mkdir()
    src=directory/'source_code';src.mkdir()
    (directory/'initial_population.json').write_text(json.dumps({'generation':0,'population':population,
          'learned_policy_initialization':'fresh_zero','members':initial_metadata},indent=2),encoding='utf-8')
    config={'experiment':'fresh_independent','source_population_file':None,'inherited_parent_count':0,
            'inherited_policy_count':0,'global_memory':'new_zero','seed':seed,'squares':squares,
            'population':population,'generations':generations,'offspring_per_parent':offspring_per_parent,
            'structural_initial_count':sum(m.source=='connected_tiling' for m in initial),
            'stochastic_initial_count':sum(m.source!='connected_tiling' for m in initial),
            'initial_origin_breakdown':initial_origin_breakdown,
            'competitive_stochastic_initial_count':competitive_stochastic_initial_count,
        'initial_relative_orientation_count':initial_relative_orientation_count,
            'competitive_stochastic_threshold_side':grid.grid_upper_side+0.4,
            'grid_upper_bound':grid.grid_upper_side,'area_lower_bound':grid.area_lower_side,
            'focused_cap':focused_cap,'cap_margin':cap_margin,
            'selection':'quality and competitive novelty only; source label ignored',
            'normal_quota':{'quality':round(.64*population),'frontier':round(.08*population)},
            'stagnating_quota':{'quality':round(.52*population),'frontier':round(.12*population)},
            'compressor':asdict(compressor),'stagnation':asdict(stagnation.settings),
            'rolling_stagnation':asdict(stagnation.window_settings),
            'note':'Known grid L is a constructed feasible baseline. No prior Gerit results used.'}
    (directory/'config.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
    history=[]
    started=time.perf_counter()
    def snapshot(g,mode,accepted,checks):
        row={'generation':g,'search_mode':mode,'best_side':best.container_side,
             'best_id':best_id,'population_best':min(p.container_side for _,p in pop),
             'selected_ids':[uid for uid,_ in pop],
             'selected_ancestry_counts':dict(Counter(ancestry[uid] for uid,_ in pop)),
             'near_best_parent_count':sum(p.container_side<=best.container_side+0.05
                                          for _,p in pop),
             'rotated_parent_count':sum(any(abs(math.sin(2*s.angle))>1e-7
                                            for s in p.squares) for _,p in pop),
             'relative_orientation_parent_count':sum(relative_angle_spread(p)>0.01
                                                     for _,p in pop),
             'stagnation_generations':g-stagnation.last_significant_generation,
             'rolling_window_gain':stagnation.window_gain,
             'weak_progress_streak':stagnation.weak_progress_streak,
             'valid_children_this_gen':accepted,
             'proposals_cumulative':stats['births'],
             'valid_children_cumulative':stats['valid'],
             'geometry_checks_cumulative':checks,
             'elapsed_seconds':time.perf_counter()-started}
        history.append(row);append_jsonl(gen_file,row);gen_file.flush()
        draw_population(images/f'gen_{g:03d}.png',pop,None)
    with (directory/'individuals.jsonl').open('w',encoding='utf-8') as ind, \
         (directory/'selection.jsonl').open('w',encoding='utf-8') as sel, \
         (directory/'generations.jsonl').open('w',encoding='utf-8') as gen_file, \
         GeometryCounter() as gate:
        for uid,p in pop:
            append_jsonl(ind,{'individual_id':uid,'generation':0,'origin':initial_kind[uid],
                'parent_ids':[],'valid':True,'side':p.container_side,'squares':[asdict(x) for x in p.squares],
                'policy':weights[uid]})
        snapshot(0,'initial',0,0)
        for generation in range(1,generations+1):
            mode=stagnation.mode(generation-1)
            old=list(pop);children=[];previous_record=best.container_side
            generation_valid=0
            for uid,parent in old:
                for _ in range(offspring_per_parent):
                    raw_before,comp_before=gate.raw,gate.comp
                    gate.phase='raw'
                    parent_cap=max(focused_cap,parent.container_side+cap_margin)
                    chance=rng.random()
                    if mode=='precision' and chance<.55:
                        raw,meta=propose_micro(parent,rng,parent_cap)
                    elif mode=='escape' and chance<.42:
                        raw,meta=propose_reconfigure(parent,rng,parent_cap)
                    elif mode=='diversify' and chance<.60:
                        raw,meta=propose_reconfigure(parent,rng,parent_cap)
                    elif mode in ('escape','diversify') and chance<.75:
                        raw,meta=propose_micro(parent,rng,parent_cap)
                    else:
                        raw,meta=propose_learned(parent,rng,parent_cap,weights[uid],controller)
                    used_raw=gate.raw-raw_before
                    candidate=raw;compression_gain=0.0;compression_meta=None
                    if raw is not None:
                        gate.phase='comp'
                        candidate,compression_meta=compress_valid(raw,rng,compressor,parent_cap)
                        compression_gain=raw.container_side-candidate.container_side
                    used_comp=gate.comp-comp_before
                    valid=candidate is not None and validate_packing(candidate,tolerance=0.0).valid
                    stats['births']+=1;mode_births[mode]+=1
                    mode_checks[mode]+=used_raw+used_comp
                    if valid:
                        stats['valid']+=1;generation_valid+=1;mode_valid[mode]+=1
                        ancestry[next_id]=ancestry[uid]
                        children.append((next_id,candidate))
                    raw_gain=(parent.container_side-raw.container_side) if raw is not None else 0.0
                    final_gain=(parent.container_side-candidate.container_side) if valid else 0.0
                    if valid and raw_gain>1e-8:stats['raw_improving']+=1
                    if valid and final_gain>1e-8:stats['final_improving']+=1
                    if valid and compression_gain>1e-8:stats['compression_improving']+=1
                    action_counts[meta['action']]+=1
                    policy,feedback=controller.update(weights[uid],meta,valid,raw_gain,
                           compression_gain,parent.container_side,used_raw,used_comp,
                           global_best_side=best.container_side,train=True)
                    if valid:weights[next_id]=policy
                    append_jsonl(ind,{'individual_id':next_id,'generation':generation,
                        'origin':'evolved','parent_ids':[uid],'valid':valid,
                        'side':candidate.container_side if valid else None,
                        'squares':[asdict(s) for s in candidate.squares] if valid else None,
                        'mutation':meta,
                        'compression':compression_meta,
                        'feedback':feedback,'mode':mode})
                    next_id+=1
            pool=old+children
            selected=select_competitive_diverse(pool,population,mode)
            topid,toppack=min(selected,key=lambda item:(item[1].container_side,item[0]))
            if toppack.container_side<best.container_side:
                best_id,best=topid,toppack
                if stagnation.reference_side-best.container_side>=stagnation.settings.significant_gain:
                    print(f'NEW BEST gen={generation} L={best.container_side:.12f}',flush=True)
            if best_id not in {uid for uid,_ in selected}:
                selected[-1]=(best_id,best)
            pop=selected
            survivors={uid for uid,_ in pop}
            for uid,p in pool:
                append_jsonl(sel,{'generation':generation,'individual_id':uid,
                      'selected':uid in survivors,'side':p.container_side})
            weights={uid:weights[uid] for uid in survivors}
            if best.container_side<previous_record-1e-10:
                mode_record_events[mode]+=1
                mode_record_gain[mode]+=previous_record-best.container_side
            old_mode=mode
            new_mode=stagnation.update(generation,best.container_side)
            if new_mode!=old_mode:
                print(f'MODE_CHANGE after_gen={generation} {old_mode}->{new_mode} '
                      f'window_gain={stagnation.window_gain} slow={stagnation.weak_progress_streak}',flush=True)
            snapshot(generation,mode,generation_valid,gate.raw+gate.comp)
            sel.flush();ind.flush()
            modes[mode]+=1
            if generation==1 or generation%10==0:
                print(f'GEN {generation}/{generations} L={best.container_side:.12f} '
                      f'mode={mode} valid={stats["valid"]}/{stats["births"]} '
                      f'checks={gate.raw+gate.comp} elapsed={time.perf_counter()-started:.1f}',flush=True)
    shapely_results=[geometry_check_shapely(p) for uid,p in pop]
    assert all(validate_packing(p,tolerance=0.0).valid for uid,p in pop)
    overlap=max(v['max_overlap_area'] for v in shapely_results if v['available'])
    outside=max(v['max_outside_area'] for v in shapely_results if v['available'])
    assert overlap<=1e-12 and outside<=1e-12
    summary={'status':'completed','experiment':'fresh_independent','generations':generations,
        'squares':squares,'population':population,'seed':seed,'offspring_per_parent':offspring_per_parent,
        'starting_structural_count':config['structural_initial_count'],
        'starting_stochastic_count':config['stochastic_initial_count'],
        'initial_origin_breakdown':initial_origin_breakdown,
        'competitive_stochastic_initial_count':competitive_stochastic_initial_count,
        'initial_relative_orientation_count':initial_relative_orientation_count,
        'final_ancestry_counts':dict(Counter(ancestry[uid] for uid,_ in pop)),
        'final_relative_orientation_parent_count':sum(relative_angle_spread(p)>0.01
                                                     for _,p in pop),
        'final_near_best_parent_count':sum(p.container_side<=best.container_side+0.05
                                         for _,p in pop),
        'inherited_parents':0,'inherited_training':False,
        'initial_best_side':best_initial,'best_side':best.container_side,
        'improvement_after_initialization':best_initial-best.container_side,
        'grid_upper_bound':grid.grid_upper_side,
        'proposals':stats['births'],'valid_children':stats['valid'],
        'invalid_children':stats['births']-stats['valid'],
        'raw_improving_children':stats['raw_improving'],
        'final_improving_children':stats['final_improving'],
        'compression_improving_children':stats['compression_improving'],
        'raw_geometric_checks':gate.raw,'compression_geometric_checks':gate.comp,
        'total_geometry_checks':gate.raw+gate.comp,
        'mode_generations':dict(modes),'mode_proposals':dict(mode_births),
        'mode_valid_children':dict(mode_valid),'mode_geometry_checks':dict(mode_checks),
        'mode_record_events':dict(mode_record_events),'mode_record_gain':dict(mode_record_gain),
        'action_proposals':dict(action_counts),'stagnation':stagnation.snapshot(),
        'controller':controller.snapshot(),
        'final_selected_max_positive_overlap_area':overlap,
        'final_selected_max_outside_area':outside,
        'best_shapely':geometry_check_shapely(best),
        'population_images':generations+1,'elapsed_seconds':time.perf_counter()-started,
        'note':'No parent, reward weights, or progress history imported. The grid bound is a legitimate constructive initialization rule.'}
    (directory/'run_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    (directory/'mode_metrics.json').write_text(json.dumps({name:summary[name] for name in (
        'mode_generations','mode_proposals','mode_valid_children',
        'mode_geometry_checks','mode_record_events','mode_record_gain')},indent=2),encoding='utf-8')
    (directory/'selected_population_final.json').write_text(json.dumps({
       'generation':generations,'selected_members':[{'individual_id':uid,
           'initial_ancestor_source':ancestry[uid],
           'container_side':p.container_side,'squares':[asdict(x) for x in p.squares],
           'policy':weights[uid]} for uid,p in pop],
       'global_policy':controller.global_policy,
       'adaptive_controller':{'reward_baselines':controller.baseline_by_context},
       'stagnation_state':{**stagnation.snapshot(),'elapsed_generations':generations},
       'initialization_kind':'fresh_mixed','squares':squares,'population':population
    },indent=2),encoding='utf-8')
    (directory/'best_result.json').write_text(json.dumps({'side':best.container_side,
         'individual_id':best_id,'squares':[asdict(x) for x in best.squares]},indent=2),encoding='utf-8')
    columns=['generation','best_side','population_best','search_mode','stagnation_generations',
             'rolling_window_gain','weak_progress_streak','near_best_parent_count',
             'rotated_parent_count','valid_children_this_gen',
             'proposals_cumulative','valid_children_cumulative','geometry_checks_cumulative','elapsed_seconds']
    with (directory/'generations.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader()
        writer.writerows([{k:record.get(k) for k in columns} for record in history])
    draw_best(directory/'best.png',best)
    (directory/'start.png').write_bytes((images/'gen_000.png').read_bytes())
    (directory/'middle.png').write_bytes((images/f'gen_{generations//2:03d}.png').read_bytes())
    (directory/'final.png').write_bytes((images/f'gen_{generations:03d}.png').read_bytes())
    _progress(directory/'progress.png',history,grid.grid_upper_side)
    (directory/'REPRODUCE.md').write_text(
       f'# Fresh Gerit: {squares} unit squares, {population} parents, {generations} generations\n\n'
       f'No population files or learning histories were imported. Random seed {seed}.\n'
       f'Initial {config["structural_initial_count"]} connected tilings and '
       f'{config["stochastic_initial_count"]} randomized arrangements.\n'
       f'Population chosen by one label-agnostic, quality-aware diversity rule.\n'
       f'{offspring_per_parent} children/parent; {stats["births"]} proposals overall.\n'
       f'Global grid L={grid.grid_upper_side} is constructed, not independently discovered.\n'
       f'Run: python scripts/run_fresh_25.py --squares {squares} --population {population} '
       f'--structural-seeds {structural_seeds} --offspring-per-parent {offspring_per_parent} '
       f'--cap-margin {cap_margin} --generations {generations} --seed {seed} '
       f'--output-dir <new directory>\n',encoding='utf-8')
    dependency_paths=[Path(__file__),ROOT/'gerit'/'fresh_population.py',
      ROOT/'gerit'/'connected_tilings.py',ROOT/'gerit'/'grid_bounds.py',
      ROOT/'gerit'/'geometry.py',ROOT/'gerit'/'selection.py',ROOT/'gerit'/'learning.py',
      ROOT/'gerit'/'local_compression.py',ROOT/'gerit'/'reward_v2.py',
      ROOT/'gerit'/'adaptive_v3.py',ROOT/'gerit'/'adaptive_v4.py',
      ROOT/'gerit'/'visualization.py',ROOT/'scripts'/'run_adaptive_tilings.py']
    for dep in dependency_paths:shutil.copyfile(dep,src/dep.name)
    verified=verify_run(directory,summary)
    (directory/'verification.json').write_text(json.dumps(verified,indent=2),encoding='utf-8')
    if make_zip:
        all_zip=directory/'complete.zip';im_zip=directory/'generation_images.zip'
        with zipfile.ZipFile(im_zip,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            for image in sorted(images.glob('gen_*.png')):archive.write(image,'generation_images/'+image.name)
        with zipfile.ZipFile(all_zip,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(directory.rglob('*')):
                if path.is_file() and path not in (all_zip,im_zip):archive.write(path,path.relative_to(directory))
        with zipfile.ZipFile(all_zip) as archive:assert archive.testzip() is None
        with zipfile.ZipFile(im_zip) as archive:assert archive.testzip() is None
        print(f'Complete archive: {all_zip}',flush=True)
        print(f'Generation images ZIP: {im_zip}',flush=True)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Fresh Gerit search: no prior genomes, 25 starting/surviving parents.')
    parser.add_argument('--squares',type=int,default=12)
    parser.add_argument('--population',type=int,default=25)
    parser.add_argument('--structural-seeds',type=int,default=7)
    parser.add_argument('--generations',type=int,default=300)
    parser.add_argument('--offspring-per-parent',type=int,default=5)
    parser.add_argument('--seed',type=int,default=2715)
    parser.add_argument('--cap-margin',type=float,default=.15)
    parser.add_argument('--output-dir',type=Path,default=Path('results/fresh12-p25-g300'))
    parser.add_argument('--no-zip',action='store_true')
    args=parser.parse_args()
    print(json.dumps(run(squares=args.squares,population=args.population,
         structural_seeds=args.structural_seeds,generations=args.generations,
         offspring_per_parent=args.offspring_per_parent,seed=args.seed,
         cap_margin=args.cap_margin,directory=args.output_dir,make_zip=not args.no_zip),indent=2))