"""Reproducible local Gerit reward-v2 continuation from saved policy genomes.

Run with `python scripts/run_continuation.py` from the cloned repository root.
The default input is the 20 selected survivors of published Round 15.
"""
from __future__ import annotations
import argparse, csv, copy, hashlib, json, random, shutil, sys, time, zipfile
from collections import Counter
from dataclasses import asdict
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
from gerit import learning as learning_mod, local_compression as compression_mod
from gerit.geometry import Packing,Square,validate_packing,square_vertices
from gerit.selection import select
from gerit.learning import propose_learned,ACTIONS
from gerit.reward_v2 import CreditController
from gerit.local_compression import CompressionSettings,compress_valid
from gerit.visualization import draw_population as draw_mosaic, draw_best, draw_progress

SOURCE=BASE/'data'/'round15_selected_population_final.json'
DEFAULT_RUN=BASE/'results'/'local_reward_v2_continuation'

DEFAULT_SEED=2607
N=20
OFFSPRING_PER_PARENT=5
SIDE_CAP=5.0

class GeometryCounter:
    def __init__(self):
        self.raw=0;self.comp=0;self.phase='raw'
    def __enter__(self):
        self.orig_learning=learning_mod.validate_packing
        self.orig_compression=compression_mod.validate_packing
        def count(*args,**kwargs):
            if self.phase=='raw': self.raw+=1
            elif self.phase=='comp':self.comp+=1
            else:raise RuntimeError('Unexpected geometry phase')
            return self.orig_learning(*args,**kwargs)
        self._count=count
        learning_mod.validate_packing=count
        compression_mod.validate_packing=count
        return self
    def __exit__(self,*exc):
        learning_mod.validate_packing=self.orig_learning
        compression_mod.validate_packing=self.orig_compression

def append_jsonl(f,item):
    f.write(json.dumps(item,ensure_ascii=False,separators=(',',':'))+'\n')

def init_pop(source_file: Path):
    # Source of truth: last run's 100 final selected members and learned genomes.
    # Source bytes and 20-member initialization are archived for provenance.
    data=source_file.read_bytes()
    source=json.loads(data)
    members=source['selected_members']
    if len(members)!=N: raise ValueError(f'Expected {N} imported parents, got {len(members)}')
    if 'global_policy' not in source: raise ValueError('Input file lacks inherited global_policy')
    all_previous=[]
    by_identity={}
    for m in members:
        p=Packing(tuple(Square(**sq) for sq in m['squares']),float(m['container_side']))
        if len(p.squares)!=12 or not validate_packing(p,tolerance=0.0).valid:
            raise ValueError(f'Invalid 12-square packing for source ID {m["individual_id"]}')
        all_previous.append((int(m['individual_id']),p))
        by_identity[id(p)]=m
        assert 'policy' in m, 'Each imported parent must have learned policy'
    if len({uid for uid,p in all_previous})!=N:
        raise ValueError('Source contains duplicate parent IDs')
    # Reuse the exact 20 selected survivors and each individual's learned policy.
    # The 18+2 quota applies to selection of each NEXT generation, not to
    # reselecting/duplicating the 20 input parents.
    initial_members=members
    population=list(all_previous)
    assert len(population)==N and len({uid for uid,p in population})==N
    policies={int(m['individual_id']):copy.deepcopy(m['policy']) for m in initial_members}
    source_sha=hashlib.sha256(data).hexdigest()
    selected_bytes=json.dumps({'generation':0, 'selected_members':initial_members,
            'global_policy':source['global_policy'], 'full_source_sha256':source_sha},
            ensure_ascii=False,indent=2).encode('utf-8')
    return population,hashlib.sha256(selected_bytes).hexdigest(),selected_bytes,policies,copy.deepcopy(source['global_policy']),source_sha,max(int(m['individual_id']) for m in members)

def geometry_check_shapely(packing):
    try:
        from shapely.geometry import Polygon,box
    except ImportError:
        return {'available':False}
    polys=[Polygon(square_vertices(s)) for s in packing.squares]
    overlaps=[polys[i].intersection(polys[j]).area for i in range(12) for j in range(i+1,12)]
    bound=box(0,0,packing.container_side,packing.container_side)
    outside=[poly.difference(bound).area for poly in polys]
    return {'available':True,'max_overlap_area':max(overlaps,default=0.0),
            'max_outside_area':max(outside,default=0.0),
            'min_square_area':min(poly.area for poly in polys),
            'max_square_area':max(poly.area for poly in polys)}

def run(generations:int=100, seed:int=DEFAULT_SEED,
        directory:Path=DEFAULT_RUN, make_zip:bool=True,
        source_file:Path=SOURCE):
    if generations < 1: raise ValueError('generations must be >= 1')
    source_file=Path(source_file).expanduser().resolve()
    if not source_file.is_file(): raise FileNotFoundError(f'Input population missing: {source_file}')
    directory=Path(directory).expanduser().resolve()
    # Never delete or silently overwrite a previous scientific run.
    if directory.exists(): raise FileExistsError(f'Output directory exists: {directory}\nPass a NEW --output-dir')
    directory.mkdir(parents=True)
    imgs=directory/'generation_images';imgs.mkdir()
    source_code=directory/'source_code';source_code.mkdir()
    pop,sha,source_bytes,source_policy,source_global_policy,source_full_sha,source_max_id=init_pop(source_file)
    (directory/'input_selected_population.json').write_bytes(source_bytes)
    (directory/'source_last_100_metadata.json').write_text(json.dumps({'source_path':str(source_file),'source_sha256':source_full_sha,'selection_rule':'all 20 previous final survivors, in original order','selected_ids':[uid for uid,p in pop]},indent=2),encoding='utf-8')
    ctl=CreditController()
    ctl.global_policy=copy.deepcopy(source_global_policy)
    compressor=CompressionSettings()
    state={uid:copy.deepcopy(source_policy[uid]) for uid,p in pop}
    rng=random.Random(seed)
    nextid=source_max_id+1
    best_id,best=min(pop,key=lambda up:up[1].container_side)
    baseline=best.container_side
    init_population_snapshot=list(pop)
    counts=Counter()
    action_counts=Counter();action_valid=Counter();action_gain=Counter()
    started=time.perf_counter();history=[]
    (directory/'config.json').write_text(json.dumps({
        'source_final_population_file':str(source_file),'source_generation':json.loads(source_file.read_text(encoding='utf-8')).get('generation','unknown'),
        'source_full_population_sha256':source_full_sha,'input_20_selected_sha256':sha,
        'selection_from_source_20':'all 20 final survivors, preserving learned policy genomes',
        'squares':12,'population':N,'generations':generations,'seed':seed,'side_cap':SIDE_CAP,
        'offspring_per_parent_per_generation':OFFSPRING_PER_PARENT,'quality_slots':18,'diversity_slots':2,
        'mutation':'10 continuous directional operator families, per-parent inherited probability genes',
        'reward_version':'CreditController v2: direct, compression & geometric cost separately',
        'local_compression_settings':asdict(compressor),
        'notes':'Exactly 20 members inherited from Round 14 final survivors; learned individual AND global policies inherited without resetting. Geometry-check counts cover module-internal validation only; independent final validation counted separately. Seed is new; not bitwise RNG continuation.'
    },indent=2,ensure_ascii=False),encoding='utf-8')
    def snapshot(gen,accepted):
        row={'generation':gen,'best_side':best.container_side,'best_id':best_id,
             'population_best':min(p.container_side for _,p in pop),
             'selected_ids':[uid for uid,p in pop],
             'valid_children':accepted,'total_births':counts['births'],
             'total_valid_children':counts['valid'],
             'raw_improving':counts['raw_improving'],'final_improving':counts['final_improving'],
             'raw_geometric_checks':gate.raw,'compression_geometric_checks':gate.comp,
             'total_geometric_checks':gate.raw+gate.comp,
             'training_global_probabilities':ctl.probabilities(ctl.new_policy(),ctl.context(best)),
             'elapsed_seconds':time.perf_counter()-started}
        history.append(row)
        append_jsonl(gen_file,row);gen_file.flush()
        draw_mosaic(imgs/f'gen_{gen:03d}.png',pop,SIDE_CAP)
    with (directory/'individuals.jsonl').open('w',encoding='utf-8') as ind, \
         (directory/'selection.jsonl').open('w',encoding='utf-8') as sel, \
         (directory/'generations.jsonl').open('w',encoding='utf-8') as gen_file, \
         GeometryCounter() as gate:
        for uid,p in pop:
            append_jsonl(ind,{'individual_id':uid,'generation':0,'origin':'imported_reward_v2_final',
               'parent_ids':[],'valid':True,'side':p.container_side,
               'squares':[asdict(s) for s in p.squares], 'policy':state[uid]})
        snapshot(0,0)
        for g in range(1,generations+1):
            old=list(pop);children=[]
            for uid,parent in old:
                for _ in range(OFFSPRING_PER_PARENT):
                    before_raw,before_comp=gate.raw,gate.comp
                    gate.phase='raw'
                    raw,meta=propose_learned(parent,rng,SIDE_CAP,state[uid],ctl)
                    used_raw=gate.raw-before_raw
                    candidate=raw
                    comp_gain=0.0
                    compression_meta=None
                    if raw is not None:
                        gate.phase='comp'
                        candidate,compression_meta=compress_valid(raw,rng,compressor,SIDE_CAP)
                        comp_gain=raw.container_side-candidate.container_side
                    used_comp=gate.comp-before_comp
                    valid=candidate is not None and validate_packing(candidate,tolerance=0.0).valid
                    counts['safety_checks']+=bool(candidate is not None)
                    if valid:
                        counts['valid']+=1
                        children.append((nextid,candidate))
                    if raw is not None:counts['raw_valid']+=1
                    counts['births']+=1
                    raw_gain=parent.container_side-raw.container_side if raw is not None else 0.0
                    final_gain=parent.container_side-candidate.container_side if valid else 0.0
                    if raw_gain>1e-8 and valid:counts['raw_improving']+=1
                    if final_gain>1e-8 and valid:counts['final_improving']+=1
                    if comp_gain>1e-8 and valid:counts['comp_improving']+=1
                    action_counts[meta['action']]+=1
                    if valid:action_valid[meta['action']]+=1
                    if valid and final_gain>1e-8:action_gain[meta['action']]+=1
                    learned_policy,feedback=ctl.update(state[uid],meta,valid,raw_gain,comp_gain,
                        parent.container_side,used_raw,used_comp,train=True)
                    if valid:state[nextid]=learned_policy
                    append_jsonl(ind,{'individual_id':nextid,'generation':g,'origin':'reward_v2_offspring',
                       'parent_ids':[uid],'valid':valid,'side':candidate.container_side if valid else None,
                       'squares':[asdict(s) for s in candidate.squares] if valid else None,
                       'mutation':meta,'compression':{'accepted_moves':compression_meta['compression_accepted'],
                           'side_gain':comp_gain} if compression_meta is not None else None,
                       'feedback':feedback})
                    nextid+=1
            pool=old+children
            winners=select([p for uid,p in pool],n=N,fitness_share=.90)
            uid_map={id(p):uid for uid,p in pool}
            pop=[(uid_map[id(p)],p) for p in winners]
            survivor_ids={uid for uid,p in pop}
            for uid,p in pool:
                append_jsonl(sel,{'generation':g,'individual_id':uid,'selected':uid in survivor_ids,
                                  'side':p.container_side})
            state={uid:state[uid] for uid in survivor_ids}
            topid,toppack=min(pop,key=lambda row:row[1].container_side)
            if toppack.container_side<best.container_side:
                best_id,best=topid,toppack
                print(f'NEW BEST gen={g} L={best.container_side:.12f}',flush=True)
            snapshot(g,len(children))
            ind.flush();sel.flush()
            if g % 10==0 or g==1:
                print(f'GEN {g}/{generations} best={best.container_side:.12f} valid={counts["valid"]}/{counts["births"]} checks={gate.raw+gate.comp} elapsed={time.perf_counter()-started:.2f}',flush=True)
    elapsed=time.perf_counter()-started
    assert len(history)==generations+1
    assert counts['births']==N*generations*OFFSPRING_PER_PARENT
    assert counts['raw_valid']==counts['valid']
    assert all(b['best_side']<=a['best_side']+1e-12 for a,b in zip(history,history[1:]))
    assert len(list(imgs.glob('gen_*.png')))==generations+1
    assert validate_packing(best,tolerance=0.0).valid
    assert best.container_side<=baseline
    # Fully validate all selected endpoint geometries outside the instrumented cost meter.
    from shapely.geometry import Polygon,box
    independent_max_intersection=0.0
    independent_max_outside=0.0
    for uid,p in pop:
        assert validate_packing(p,tolerance=0.0).valid
        v=geometry_check_shapely(p)
        if v['available']:
            independent_max_intersection=max(independent_max_intersection,v['max_overlap_area'])
            independent_max_outside=max(independent_max_outside,v['max_outside_area'])
    report={
        'status':'completed','generations':generations,'population':N,'squares':12,
        'seed':seed,'source_round':'user_supplied_population_file',
        'source_population_sha256':sha,'source_full_population_sha256':source_full_sha,
        'initial_parent_ids':[uid for uid,p in init_population_snapshot],
        'parent_selection':{'source':'all imported final survivors','per_generation_quality':18,'per_generation_diversity':2,'method':'Gerit select()'},
        'initial_best_side':baseline,'best_side':best.container_side,
        'improvement':baseline-best.container_side,
        'best_individual_id':best_id,'elapsed_seconds':elapsed,
        'proposals':counts['births'],'valid_children':counts['valid'],
        'invalid_children':counts['births']-counts['valid'],
        'raw_improving_children':counts['raw_improving'],
        'final_improving_children':counts['final_improving'],
        'compression_improving_children':counts['comp_improving'],
        'raw_geometry_checks':gate.raw,'compression_geometry_checks':gate.comp,
        'total_geometry_checks':gate.raw+gate.comp,
        'safety_geometry_checks':counts['safety_checks'],
        'action_proposals':dict(action_counts),'action_valid':dict(action_valid),
        'action_improving':dict(action_gain),
        'controller':ctl.snapshot(),
        'best_shapely':geometry_check_shapely(best),
        'final_selected_max_positive_overlap_area':independent_max_intersection,
        'final_selected_max_outside_area':independent_max_outside,
        'population_images':len(history),
        'warning':'Single-seed continuation, not a global optimum proof or controlled experiment. All 20 imported parents and individual/global learned policy genomes retained.'}
    (directory/'run_summary.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    (directory/'best_result.json').write_text(json.dumps({'individual_id':best_id,'side':best.container_side,
       'squares':[asdict(s) for s in best.squares]},indent=2),encoding='utf-8')
    (directory/'selected_population_final.json').write_text(json.dumps({
        'generation':generations,'selected_members':[{'individual_id':uid,
           'container_side':p.container_side,'squares':[asdict(s) for s in p.squares],
           'policy':state[uid]} for uid,p in pop],
        'global_policy':ctl.global_policy
    },indent=2),encoding='utf-8')
    with (directory/'generations.csv').open('w',newline='') as f:
        cols=['generation','best_side','population_best','valid_children','total_births','total_valid_children',
              'raw_improving','final_improving','raw_geometric_checks','compression_geometric_checks',
              'total_geometric_checks','elapsed_seconds']
        writer=csv.DictWriter(f,fieldnames=cols);writer.writeheader()
        writer.writerows([{k:row.get(k) for k in cols} for row in history])
    draw_best(directory/'best.png',best)
    (directory/'start.png').write_bytes((imgs/'gen_000.png').read_bytes())
    (directory/'middle.png').write_bytes((imgs/f'gen_{generations//2:03d}.png').read_bytes())
    (directory/'final.png').write_bytes((imgs/f'gen_{generations:03d}.png').read_bytes())
    draw_progress(directory/'progress.png',history)
    with (directory/'REPRODUCE.md').open('w',encoding='utf-8') as f:
        f.write(f'''# Gerit reward-v2: 12 unit squares, 20 parents, {generations} full generations

## Input and exact protocol
* Read 20 last selected members (with learned policies) from `{source_file}`; SHA-256 of complete source: `{source_full_sha}`.
* Inherit **all 20 imported survivors unchanged**, retaining genuine IDs and associated policy genes; apply **18 quality + 2 diversity selection** in each subsequent generation.
* Initial 20 selected snapshot and SHA-256: `{sha}` (see `input_selected_population.json`).
* Inherit **both** each selected parent's existing mutation policy and the trained `global_policy`; no resets or reinitialization.
* Seed: `{seed}`; 18 quality + 2 diversity survivors; **{OFFSPRING_PER_PARENT}** child proposals per parent (100 each generation).
* Movement: 10 probabilistic motion families; inherited directional/size learned weights plus global learned probabilities.
* Reward: v2 separates direct mutation gain, additional local compression gain, and SAT validator-call costs.
* Local compressor: up to 35 trials per valid raw child.
* Births {counts['births']}; valid {counts['valid']}; invalid {counts['births']-counts['valid']}.
* Internal validation calls: {gate.raw} raw + {gate.comp} local compression; another {counts['safety_checks']} final safety checks separate.
* {generations+1} real PNG snapshots with **20** individuals each (gen_000 through gen_{generations:03d}).
* Independent Shapely checks on all final 20 survivors: maximum overlap {independent_max_intersection}, maximum outside area {independent_max_outside}.
* The three-rows-of-4 unit squares grid benchmark L=4 remains the reference.
* This continuation alone does not prove reward-v2's causal advantage over frozen weights.

## Files
* `individuals.jsonl`: {N} imported parents plus {counts['births']} attempted offspring with lineage and learning feedback.
* `selection.jsonl`: all selection decisions across {generations} generations.
* `generations.jsonl`, `generations.csv`: generation history and evaluation costs.
* `selected_population_final.json`: 20 genuinely selected genomes **with inherited policy weights**.
* `run_summary.json`, `best_result.json`, `verification.json`: measured outcomes and validation.
* `source_code/`: local copy of code (does not include the whole Git history).
''')
    deps=[Path(__file__),BASE/'gerit'/'geometry.py',BASE/'gerit'/'selection.py',
          BASE/'gerit'/'learning.py',BASE/'gerit'/'local_compression.py',
          BASE/'gerit'/'reward_v2.py',BASE/'gerit'/'visualization.py',Path(__file__)]
    for path in deps:
        shutil.copyfile(path,source_code/path.name)
    verification=verify_run(directory,report)
    (directory/'verification.json').write_text(json.dumps(verification,indent=2,ensure_ascii=False),encoding='utf-8')
    if make_zip:
        full_zip=directory/'complete.zip'
        images_zip=directory/'generation_images.zip'
        with zipfile.ZipFile(images_zip,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for p in sorted(imgs.glob('gen_*.png')):
                z.write(p,arcname='generation_images/'+p.name)
        with zipfile.ZipFile(full_zip,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for p in sorted(directory.rglob('*')):
                if p.is_file() and p not in (full_zip,images_zip):
                    z.write(p,p.relative_to(directory))
        for p in (images_zip,full_zip):
            with zipfile.ZipFile(p) as z:
                if z.testzip() is not None: raise RuntimeError('ZIP corruption: '+str(p))
        print(f'Complete archive: {full_zip}', flush=True)
        print(f'Generation images ZIP: {images_zip}', flush=True)
    return report

def verify_run(directory,report):
    def readj(name):
        with (directory/name).open(encoding='utf-8') as f:return [json.loads(x) for x in f if x.strip()]
    rows=readj('generations.jsonl')
    inds=readj('individuals.jsonl')
    sels=readj('selection.jsonl')
    final=json.loads((directory/'selected_population_final.json').read_text())
    gids={r['individual_id'] for r in inds}
    assert len(rows)==report['generations']+1
    assert len(inds)==N+report['proposals']
    assert all((len(r['selected_ids'])==N) for r in rows)
    assert [r['generation'] for r in rows]==list(range(report['generations']+1))
    assert len(list((directory/'generation_images').glob('gen_*.png')))==len(rows)
    assert len(final['selected_members'])==N
    for r in inds:
        if r['generation']>0:
            assert len(r['parent_ids'])==1 and r['parent_ids'][0] in gids
            assert r['parent_ids'][0]<r['individual_id']
        if r['valid']:
            p=Packing(tuple(Square(**sq) for sq in r['squares']),r['side'])
            assert validate_packing(p,tolerance=0.0).valid
    assert len(sels)==report['generations']*N+report['valid_children']
    assert report['final_selected_max_positive_overlap_area']<=1e-12
    assert report['final_selected_max_outside_area']<=1e-12
    return {'status':'verified','generation_records':len(rows),'individual_records':len(inds),
            'selection_records':len(sels),'image_count':len(rows),'selected_final':N,
            'positive_shapely_overlap_area_max':report['final_selected_max_positive_overlap_area'],
            'out_of_bounds_area_max':report['final_selected_max_outside_area'],
            'raw_checks':report['raw_geometry_checks'],
            'compression_checks':report['compression_geometry_checks']}

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--input',type=Path,default=SOURCE,help='Previous selected_population_final.json (with policy weights)')
    ap.add_argument('--generations',type=int,default=100)
    ap.add_argument('--seed',type=int,default=DEFAULT_SEED)
    ap.add_argument('--output-dir',type=Path,default=DEFAULT_RUN)
    ap.add_argument('--no-zip',action='store_true')
    args=ap.parse_args()
    print(json.dumps(run(args.generations,args.seed,args.output_dir,not args.no_zip,args.input),indent=2))