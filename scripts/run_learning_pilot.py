"""Paired 12-square learning-policy pilot from identical Round 13 survivors.

Both arms: 100 parents, one birth proposal per parent, 90% fitness + 10%
structural diversity. Arm A inherits learned policy genes; arm B uses the
previous fixed coordinated+compression operator. Seed and initial state fixed;
internal SAT evaluation budgets differ and a single seed is not causal proof.
"""
from __future__ import annotations
from pathlib import Path
from dataclasses import asdict
import hashlib,json,math,random,csv,zipfile,time,sys,shutil
from PIL import Image,ImageDraw
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from gerit.geometry import Square,Packing,validate_packing,square_vertices
from gerit.selection import select
from gerit.learning import LearningController,LearningSettings,ACTIONS,propose_learned
from gerit.coordinated import CoordinatedController,mutate_coordinated
from gerit.local_compression import CompressionSettings,compress_valid

SOURCE_ZIP=Path('/mnt/data/Gerit_round13_12squares_100_generations.zip')
DEST=Path('/mnt/data/Gerit_learning_12squares_pilot')
OUTPUT_ZIP=Path('/mnt/data/Gerit_learning_12squares_pilot.zip')
SEED=2026102601
GENERATIONS=20
POP=100
SIDE_CAP=5.0
COMP_SETTINGS=CompressionSettings()


def source_members():
    with zipfile.ZipFile(SOURCE_ZIP) as z:
        matches=[n for n in z.namelist() if n.endswith('/selected_population_final.json')]
        assert len(matches)==1
        b=z.read(matches[0]);record=json.loads(b)
        assert len(record['selected_members'])==POP
        return record['selected_members'],hashlib.sha256(b).hexdigest()


def draw_mosaic(path:Path,pop:list[tuple[int,Packing]],side=5.0):
    columns=10;tile=124;plot=95;margin=12
    im=Image.new('RGB',(columns*tile,math.ceil(len(pop)/columns)*tile),'white')
    d=ImageDraw.Draw(im)
    palette=['#6699cc','#6fba96','#eeb76b','#b494d5','#db8593','#b5bf77','#77b9c2','#bbafa0','#d9aa70','#a1a0df','#7cc4a1','#c88e7e']
    for index,(uid,p) in enumerate(pop):
        ox=(index%columns)*tile+margin;oy=(index//columns)*tile+margin
        d.rectangle([ox,oy,ox+plot,oy+plot],outline='#344455',width=2)
        for i,s in enumerate(p.squares):
            vs=[(round(ox+x/side*plot),round(oy+(side-y)/side*plot)) for x,y in square_vertices(s)]
            d.polygon(vs,fill=palette[i%len(palette)])
            d.line(vs+[vs[0]],fill='#293a47',width=1)
        d.text((ox,oy+plot+2),f'L={p.container_side:.4f}',fill='#222222')
    im.save(path)


def draw_best(path:Path,p:Packing):
    fig,ax=plt.subplots(figsize=(5.8,5.8))
    colors=['tab:blue','tab:orange','tab:green','tab:red','tab:purple','tab:brown','tab:pink','tab:gray','tab:olive','tab:cyan']
    for i,s in enumerate(p.squares):
        vs=square_vertices(s); xs=[a for a,b in vs]+[vs[0][0]];ys=[b for a,b in vs]+[vs[0][1]]
        ax.fill(xs,ys,color=colors[i%len(colors)],alpha=.4)
        ax.plot(xs,ys,color=colors[i%len(colors)],linewidth=1.5)
        ax.text(s.x,s.y,str(i+1),ha='center',va='center',fontsize=8)
    L=p.container_side
    ax.plot([0,L,L,0,0],[0,0,L,L,0],color='#333333')
    ax.set(xlim=(-.05,L+.05),ylim=(-.05,L+.05),title=f'Learned mutation, 12 squares\nBest side = {L:.9f}')
    ax.set_aspect('equal')
    fig.tight_layout();fig.savefig(path,dpi=160);plt.close(fig)


def jsonl(handle, item):
    handle.write(json.dumps(item,ensure_ascii=False,separators=(',',':'))+'\n')


def run_arm(name:str,src:list[dict],sha:str):
    learning=name in ('learned','frozen')
    train_policy=(name=='learned')
    folder=DEST/name
    folder.mkdir(parents=True)
    images=folder/'generation_images';images.mkdir()
    rng=random.Random(SEED)
    ctl=LearningController() if learning else CoordinatedController()
    policy_by_id={}
    pop=[]
    next_id=max(int(m['individual_id']) for m in src)+1
    for m in src:
        p=Packing(tuple(Square(**s) for s in m['squares']),float(m['container_side']))
        assert validate_packing(p,tolerance=0.0).valid
        uid=int(m['individual_id'])
        pop.append((uid,p))
        if learning:policy_by_id[uid]=ctl.new_policy()
    assert len(pop)==POP
    start_side=min(p.container_side for _,p in pop)
    best_uid,best=min(pop,key=lambda x:x[1].container_side)
    count_valid=count_invalid=0
    local_trials=local_accepted=0
    history=[]
    clock=time.perf_counter()
    with (folder/'individuals.jsonl').open('w',encoding='utf-8') as f, (folder/'generations.jsonl').open('w',encoding='utf-8') as gens, (folder/'selection.jsonl').open('w',encoding='utf-8') as sel:
        for uid,p in pop:
            jsonl(f,{'id':uid,'generation':0,'parents':[],'origin':'round13_imported','valid':True,
                     'L':p.container_side,'squares':[asdict(s) for s in p.squares]})

        def snapshot(g, nvalid):
            row={'generation':g,'best_side':best.container_side,'best_id':best_uid,
                 'population_best':min(p.container_side for _,p in pop),
                 'selected_ids':[uid for uid,_ in pop],
                 'valid_children_this_gen':nvalid,'cumulative_valid':count_valid,
                 'cumulative_invalid':count_invalid,'compression_trials':local_trials,
                 'elapsed_seconds':time.perf_counter()-clock}
            if learning:
                row['policy_probabilities']=ctl.probabilities(ctl.new_policy(),ctl.context(best))
                row['learning_attempts']=ctl.proposals
            jsonl(gens,row);gens.flush();history.append(row)
            draw_mosaic(images/f'gen_{g:03d}.png',pop,SIDE_CAP)
        snapshot(0,0)
        for g in range(1,GENERATIONS+1):
            old=list(pop);kids=[]
            for parent_id,parent in old:
                if learning:
                    original=policy_by_id[parent_id]
                    raw,meta=propose_learned(parent,rng,SIDE_CAP,original,ctl)
                else:
                    raw,meta=mutate_coordinated(parent,rng,SIDE_CAP,ctl)
                candidate=raw
                comp_gain=0.0
                if raw is not None:
                    candidate,compression_meta=compress_valid(raw,rng,COMP_SETTINGS,SIDE_CAP)
                    local_trials+=compression_meta['compression_trials']
                    local_accepted+=compression_meta['compression_accepted']
                    comp_gain=raw.container_side-candidate.container_side
                    meta['compression']= {'trials':compression_meta['compression_trials'],
                                         'accepted':compression_meta['compression_accepted'],
                                         'side_gain':comp_gain}
                valid=candidate is not None and validate_packing(candidate,tolerance=0.0).valid
                if learning:
                    if train_policy:
                        child_policy,feedback=ctl.update(original,meta,valid,
                            parent.container_side-raw.container_side if raw is not None else 0.0,
                            comp_gain,parent.container_side)
                        meta['feedback']=feedback
                    else:
                        child_policy=original  # immutable-by-convention, never updated
                        meta['feedback']={'training_enabled':False,'reward':0.0}
                uid=next_id;next_id+=1
                if valid:
                    count_valid+=1;kids.append((uid,candidate))
                    if learning:policy_by_id[uid]=child_policy
                else:count_invalid+=1
                jsonl(f,{'id':uid,'generation':g,'parents':[parent_id],'origin':name,
                          'valid':valid,'L':candidate.container_side if valid else None,
                          'squares':[asdict(s) for s in candidate.squares] if valid else None,
                          'mutation':meta})
            pool=old+kids
            winners=select([p for uid,p in pool],n=POP,fitness_share=.90)
            ids={id(p):uid for uid,p in pool}
            pop=[(ids[id(p)],p) for p in winners]
            selected={uid for uid,_ in pop}
            for uid,p in pool:
                jsonl(sel,{'generation':g,'id':uid,'selected':uid in selected,'L':p.container_side})
            current_uid,current=min(pop,key=lambda x:x[1].container_side)
            if current.container_side<best.container_side:
                best_uid,best=current_uid,current
            if learning:
                # Collect only live policies; rejected proposals still taught the global memory.
                policy_by_id={uid:policy_by_id[uid] for uid in selected}
            snapshot(g,len(kids))
            f.flush();sel.flush()
            if g in (1,5,10,15,20):
                print(f'[{name}] {g}/{GENERATIONS} best={best.container_side:.12f} valid={count_valid} direct_improve={ctl.improved_mutation if learning else "n/a"} seconds={time.perf_counter()-clock:.1f}',flush=True)
    # additional independent validations
    assert all(history[i]['best_side']<=history[i-1]['best_side']+1e-12 for i in range(1,len(history)))
    assert count_valid+count_invalid==POP*GENERATIONS
    assert len(list(images.glob('gen_*.png')))==GENERATIONS+1
    assert len({uid for uid,p in pop})==POP
    summary={'arm':name,'policy_training_enabled':train_policy,'source_population_sha256':sha,'seed':SEED,
             'generations':GENERATIONS,'population':POP,'quality_slots':90,'diversity_slots':10,
             'offspring_per_parent':1,'best_side_start':start_side,'best_side_end':best.container_side,
             'end_best_id':best_uid,'accepted':count_valid,'rejected':count_invalid,
             'local_compression_trials':local_trials,'local_compression_accepted':local_accepted,
             'elapsed_seconds':time.perf_counter()-clock,
             'best_valid':asdict(validate_packing(best,tolerance=0.0)),
             'learning_stats':ctl.snapshot() if learning else None,
             'note':'Equal number of offspring proposals but unequal geometric-check / compression budgets; one seed only.'}
    (folder/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
    (folder/'selected_population_final.json').write_text(json.dumps({'generation':GENERATIONS,
         'selected_members':[{'individual_id':uid,'container_side':p.container_side,
                              'squares':[asdict(s) for s in p.squares],
                              **({'policy':policy_by_id[uid]} if learning else {})}
                              for uid,p in pop],
         **({'global_learning_policy':ctl.global_policy} if learning else {})},indent=2),encoding='utf-8')
    (folder/'best_result.json').write_text(json.dumps({'id':best_uid,'side':best.container_side,
        'squares':[asdict(s) for s in best.squares]},indent=2),encoding='utf-8')
    draw_best(folder/'best.png',best)
    with (folder/'generations.csv').open('w',newline='') as fd:
        writer=csv.writer(fd);writer.writerow(['generation','best_side','valid_children','elapsed_seconds'])
        for row in history:writer.writerow([row['generation'],row['best_side'],row['valid_children_this_gen'],row['elapsed_seconds']])
    return summary,history


def main():
    if DEST.exists():shutil.rmtree(DEST)
    DEST.mkdir()
    src,sha=source_members()
    (DEST/'input_selected_population.json').write_text(json.dumps({'generation':100,'selected_members':src},indent=2),encoding='utf-8')
    learned,lh=run_arm('learned',src,sha)
    baseline,bh=run_arm('baseline',src,sha)
    plt.figure(figsize=(7.2,4))
    plt.plot([x['generation'] for x in lh],[x['best_side'] for x in lh],label='Inherited learning policy')
    plt.plot([x['generation'] for x in bh],[x['best_side'] for x in bh],label='Fixed coordinated baseline')
    plt.xlabel('Generation');plt.ylabel('Best side L');plt.legend();plt.title('12 squares: matched starting population and birth proposals')
    plt.tight_layout();plt.savefig(DEST/'comparison.png',dpi=175);plt.close()

    startp=lh[0]['policy_probabilities'];endp=lh[-1]['policy_probabilities']
    names=list(ACTIONS)
    fig,ax=plt.subplots(figsize=(9.5,4))
    xs=range(len(names))
    ax.bar([i-.18 for i in xs],[startp[x] for x in names],width=.35,label='Start')
    ax.bar([i+.18 for i in xs],[endp[x] for x in names],width=.35,label='End')
    ax.set_xticks(list(xs),names,rotation=30,ha='right');ax.set_ylabel('Probability')
    ax.set_title('Global mutation-policy probabilities: start vs end')
    ax.legend();fig.tight_layout();fig.savefig(DEST/'learned_probabilities.png',dpi=160);plt.close(fig)

    # Independent Shapely check of best learned candidate.
    try:
        from shapely.geometry import Polygon
        p=json.loads((DEST/'learned/best_result.json').read_text())
        polys=[Polygon(square_vertices(Square(**sq))) for sq in p['squares']]
        max_overlap=max(polys[i].intersection(polys[j]).area for i in range(len(polys)) for j in range(i+1,len(polys)))
        independent={'shapely_available':True,'max_pairwise_overlap_area':max_overlap}
    except ImportError:
        independent={'shapely_available':False}

    report={'experiment':'Gerit: inheritable operator/magnitude/direction learning on 12 squares',
           'description':'A real two-arm seeded pilot; baseline and learning use same 100 starting geometries, one offspring per parent, 90/10 selection. Internal evaluation budgets differ.',
           'learned':learned,'baseline':baseline,'independent_geometry_check':independent,
           'caveat':'One fixed seed, 20 generations, unequal geometric checks; do not interpret as statistical superiority.'}
    (DEST/'comparison_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    (DEST/'README.md').write_text('# Inheritable probabilistic policy pilot\n\n'
        'This records a real controlled-start 12-square benchmark with equal child proposal count.\n'
        'Learning policy genes (action-family logits, direction logits and continuous-step-size bin logits)\n'
        'are attached to each child, while global policy learns from successes AND failures.\n'
        'Reward uses a reduction in bounding side relative to own parent. Compression-only gains\n'
        'receive lower credit. No learning claim from validity alone.\n\n'
        'The given comparison has only one seed and unequal internal geometry-check budgets.\n'
        'Exact starting populations, source code, JSONL records, learned policies, and plots are preserved.\n',encoding='utf-8')
    source_dir=DEST/'source_code';shutil.copytree(ROOT/'gerit',source_dir/'gerit')
    shutil.copy2(Path(__file__),source_dir/'run_learning_pilot.py')
    shutil.copytree(ROOT/'tests',source_dir/'tests')
    with zipfile.ZipFile(OUTPUT_ZIP,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for f in DEST.rglob('*'):
            if f.is_file():z.write(f,f.relative_to(DEST.parent))
    print(json.dumps({'learned_best':learned['best_side_end'],'baseline_best':baseline['best_side_end'],
        'learned_accepted':learned['accepted'],'baseline_accepted':baseline['accepted'],
        'zip':str(OUTPUT_ZIP)},indent=2),flush=True)

if __name__=='__main__':main()