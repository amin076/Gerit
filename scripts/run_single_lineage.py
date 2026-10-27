"""Single-parent, ten-offspring, strict-improvement Gerit trajectory experiment."""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import shutil
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw
from gerit.geometry import Packing, Square, square_vertices, validate_packing
from gerit.fresh_population import make_fresh_population
from gerit.adaptive_v4 import AdaptiveCreditController, normalize_policy, propose_micro, propose_reconfigure
from gerit.learning import propose_learned
from gerit.contact_relocation import propose_contact_relocate
from gerit.local_compression import CompressionSettings, compress_valid
from scripts.run_adaptive_tilings import GeometryCounter

COLORS = ('#6699cc','#6fba96','#eeb76b','#b494d5','#db8593',
          '#b5bf77','#77b9c2','#bbafa0','#d9aa70','#a1a0df',
          '#7cc4a1','#c88e7e')


def load_start(args):
    """Read a real saved survivor OR make a new non-grid starting parent."""
    if args.resume_packing:
        source = json.loads(Path(args.resume_packing).read_text(encoding='utf-8'))
        if not all(k in source for k in ('squares','container_side')):
            raise ValueError('resume-packing needs container_side and squares')
        packing = Packing(tuple(Square(**sq) for sq in source['squares']),
                          float(source['container_side']))
        provenance = {'kind':'resumed_final_packing',
                      'file':str(Path(args.resume_packing).resolve()),
                      'initial_side':packing.container_side,
                      'policy_inherited':source.get('policy') is not None,
                      'global_policy_inherited':source.get('global_policy') is not None}
        return packing, source.get('policy'), source.get('global_policy'), provenance
    if args.input:
        source = json.loads(Path(args.input).read_text(encoding='utf-8'))
        members = source['selected_members']
        ordered = sorted(members, key=lambda m: (float(m['container_side']), int(m['individual_id'])))
        if not 0 <= args.parent_rank < len(ordered):
            raise ValueError('parent-rank is outside the imported population')
        member = ordered[args.parent_rank]
        packing = Packing(tuple(Square(**s) for s in member['squares']),
                          float(member['container_side']))
        provenance = {'kind':'imported','file':str(Path(args.input).resolve()),
                      'parent_rank':args.parent_rank,'individual_id':member['individual_id']}
        return packing, member.get('policy'), source.get('global_policy'), provenance
    pool = make_fresh_population(args.squares, 20, 6, args.seed)
    # Avoid the already-optimal-on-the-grid starting control: choose a fresh
    # compact, non-constructive packing, to inspect an actual descent.
    candidates = [m for m in pool if m.source != 'connected_tiling']
    member = min(candidates, key=lambda m: m.packing.container_side)
    return member.packing, None, None, {'kind':'fresh','source':member.source}


def render(path: Path, packing: Packing, initial_side: float, step: int,
           total: int, gain: float, accepted: bool) -> None:
    """Constant camera scale: no artificial square motion from auto-zoom."""
    size, left, top, extent = 800, 75, 105, 640
    image = Image.new('RGB', (size,size), '#f9fafb')
    draw = ImageDraw.Draw(image)
    scale_side = initial_side + 0.15
    sc = extent / scale_side
    def xy(x,y):
        return (round(left+x*sc), round(top+(scale_side-y)*sc))
    side = packing.container_side
    draw.rectangle((*xy(0,side), *xy(side,0)), outline='#263445', width=3)
    for i,sq in enumerate(packing.squares):
        pts=[xy(x,y) for x,y in square_vertices(sq)]
        draw.polygon(pts, fill=COLORS[i%len(COLORS)])
        draw.line(pts+[pts[0]], fill='#263445', width=2)
    draw.text((left,20),f'Gerit single lineage | step {step:03d}/{total:03d}',fill='#18212d')
    draw.text((left,43),f'L={side:.10f}  delta={gain:.10f}  {"accepted" if accepted else "stalled"}',fill='#18212d')
    draw.text((left,765),f'Fixed scale: initial L={initial_side:.7f}',fill='#526171')
    image.save(path)


def _distance(a: Packing, b: Packing) -> float:
    """Compare actual poses, not just the enclosing sides."""
    from gerit.selection import packing_distance
    return packing_distance(a,b)


def _seed_branches(parent, parent_policy, candidates, args):
    """Keep incumbent and up to N-1 VALID geometrically different child states.

    Candidates may have *worse* side; the allowed regression is bounded.
    The cap on parallel lineages is floor(children/2), not an ongoing quota.
    """
    target = min(args.branches, max(1,args.children//2))
    selected = [{'packing':parent,'policy':parent_policy,'id':0,'stalled':0}]
    eligible = [(p,policy) for p,policy in candidates
                if p.container_side <= parent.container_side + args.branch_max_regression
                and _distance(p,parent) > args.branch_min_distance]
    while len(selected)<target and eligible:
        def score(item):
            p,_ = item
            distance = min(_distance(p,x['packing']) for x in selected)
            return (distance, -p.container_side)
        eligible.sort(key=score,reverse=True)
        p,pol = eligible.pop(0)
        if min(_distance(p,x['packing']) for x in selected) < args.branch_min_distance:
            continue
        selected.append({'packing':p,'policy':pol,'id':len(selected),'stalled':0})
    return selected


def _propose_batch(parent, policy, stalled, controller, rng, compressor, gate, args,
                   archive_side):
    mode = ('normal' if stalled < 40 else 'precision' if stalled < 80 else
            'escape' if stalled < 120 else 'diversify')
    best = None
    best_policy = None
    best_index = None
    valid_count = improved_count = 0
    candidates = []
    for index in range(1,args.children+1):
        before_raw,before_comp=gate.raw,gate.comp
        gate.phase='raw'
        cap=parent.container_side + args.cap_margin
        roll=rng.random()
        if mode=='precision' and roll<.55:
            raw,meta=propose_micro(parent,rng,cap)
        elif mode in ('escape','diversify') and roll<(.42 if mode=='escape' else .60):
            raw,meta=(propose_contact_relocate(parent,rng,cap)
                      if rng.random()<args.contact_probability
                      else propose_reconfigure(parent,rng,cap))
        elif mode in ('escape','diversify') and roll<.75:
            raw,meta=propose_micro(parent,rng,cap)
        else:
            raw,meta=propose_learned(parent,rng,cap,policy,controller)
        candidate=raw
        compression_gain=0.0
        gate.phase='comp'
        if raw is not None:
            candidate,_=compress_valid(raw,rng,compressor,cap)
            compression_gain=raw.container_side-candidate.container_side
        raw_checks,comp_checks=gate.raw-before_raw,gate.comp-before_comp
        valid=candidate is not None and validate_packing(candidate,tolerance=0.0).valid
        raw_gain=parent.container_side-raw.container_side if raw is not None else 0.0
        candidate_policy,_=controller.update(policy,meta,valid,raw_gain,
                    compression_gain,parent.container_side,raw_checks,comp_checks,
                    global_best_side=archive_side,train=True)
        if valid:
            valid_count+=1
            candidates.append((candidate,candidate_policy))
            gain=parent.container_side-candidate.container_side
            if gain>args.improvement_epsilon:
                improved_count+=1
                if best is None or candidate.container_side<best.container_side:
                    best,best_policy,best_index=candidate,candidate_policy,index
    return {'mode':mode,'best':best,'policy':best_policy,'best_index':best_index,
            'valid':valid_count,'improving':improved_count,'candidates':candidates}


def run(args):
    if args.steps<1 or args.children<1 or args.fps<1:
        raise ValueError('steps, children and fps must be positive')
    if not 1<=args.branches<=max(1,args.children//2):
        raise ValueError('branches must be 1..floor(children/2)')
    if args.stagnation_window<1 or args.branch_generations<1:
        raise ValueError('stagnation-window and branch-generations must be positive')
    if any(not math.isfinite(x) or x<0 for x in
           (args.significant_gain,args.branch_max_regression,
            args.branch_min_distance,args.improvement_epsilon,args.cap_margin)):
        raise ValueError('thresholds and margins must be finite and nonnegative')
    if not 0<=args.contact_probability<=1:
        raise ValueError('contact-probability must be 0..1')
    output=Path(args.output_dir).expanduser().resolve()
    if output.exists():
        raise FileExistsError(f'Output already exists: {output}')
    parent,inherited_policy,inherited_global,provenance=load_start(args)
    if not validate_packing(parent,tolerance=0.0).valid:
        raise ValueError('Initial packing fails strict geometry validation')
    controller=AdaptiveCreditController()
    if inherited_global is not None:
        controller.global_policy=normalize_policy(inherited_global)
    policy=(normalize_policy(inherited_policy) if inherited_policy is not None
            else controller.new_policy())
    rng=random.Random(args.seed+7919)
    compressor=CompressionSettings()
    initial_side=parent.container_side
    archive=parent
    archive_policy=policy
    checkpoint_side=parent.container_side
    checkpoint_step=0
    stalled=0
    branches=None
    branch_age=0
    branch_events=[]
    rows=[]
    accepted_total=valid_total=improving_total=0
    proposal_total=0
    start=time.perf_counter()
    output.mkdir(parents=True)
    frames=output/'frames'
    frames.mkdir()
    render(output/'initial.png',parent,initial_side,0,args.steps,0.,False)
    with GeometryCounter() as gate, (output/'trajectory.jsonl').open('w',encoding='utf-8') as log:
        for step in range(1,args.steps+1):
            before=parent.container_side
            active=branches if branches is not None else [
                {'packing':parent,'policy':policy,'id':0,'stalled':stalled}]
            valid_count=improving_count=0
            accepted_count=0
            all_candidates=[]
            current_modes=[]
            for lineage in active:
                prior=lineage['packing']
                result=_propose_batch(prior,lineage['policy'],lineage['stalled'],
                                      controller,rng,compressor,gate,args,
                                      archive.container_side)
                proposal_total+=args.children
                valid_count+=result['valid']
                improving_count+=result['improving']
                current_modes.append(result['mode'])
                if branches is None:
                    all_candidates=result['candidates']
                if result['best'] is not None:
                    lineage['packing']=result['best']
                    lineage['policy']=result['policy']
                    lineage['stalled']=0
                    accepted_count+=1
                else:
                    lineage['stalled']+=1
                if lineage['packing'].container_side<archive.container_side:
                    archive=lineage['packing']
                    archive_policy=lineage['policy']
            accepted_total+=accepted_count
            valid_total+=valid_count
            improving_total+=improving_count
            event=''
            if branches is None:
                parent,policy=active[0]['packing'],active[0]['policy']
                stalled=active[0]['stalled']
                # Check the TOTAL gain across the last fixed window, not
                # merely whether an improvement occurred in the last step.
                if (args.branches>1 and step-checkpoint_step>=args.stagnation_window):
                    gain=checkpoint_side-archive.container_side
                    if gain<args.significant_gain:
                        newborn=_seed_branches(parent,policy,all_candidates,args)
                        if len(newborn)>1:
                            branches=newborn
                            branch_age=0
                            event='branch_start'
                            branch_events.append({'type':event,'step':step,
                                'count':len(branches),'checkpoint_gain':gain,
                                'sides':[x['packing'].container_side for x in branches]})
                        else:
                            event='branch_seed_shortfall'
                            branch_events.append({'type':event,'step':step,
                                'count':len(newborn),'checkpoint_gain':gain})
                    checkpoint_side=archive.container_side
                    checkpoint_step=step
            else:
                branch_age+=1
                # For visual continuity, follow the current BEST temporary
                # branch; independent archived best is never lost.
                observed=min(branches,key=lambda b:(b['packing'].container_side,b['id']))
                parent,policy=observed['packing'],observed['policy']
                if branch_age>=args.branch_generations:
                    champion=min(branches,key=lambda b:(b['packing'].container_side,b['id']))
                    winner_side=champion['packing'].container_side
                    if archive.container_side<=winner_side:
                        parent,policy=archive,archive_policy
                        winner='archive'
                    else:
                        parent,policy=champion['packing'],champion['policy']
                        winner=champion['id']
                    event='branch_end'
                    branch_events.append({'type':event,'step':step,'winner':winner,
                         'winner_side':parent.container_side,
                         'branch_final_sides':[x['packing'].container_side for x in branches]})
                    branches=None
                    stalled=0
                    checkpoint_side=archive.container_side
                    checkpoint_step=step
            if not validate_packing(parent,tolerance=0.0).valid:
                raise AssertionError('Invalid selected packing')
            if not validate_packing(archive,tolerance=0.0).valid:
                raise AssertionError('Invalid archive')
            record={'step':step,
                    'phase':'branching' if branches is not None or event=='branch_end' else 'single',
                    'mode':','.join(current_modes),
                    'side_before':before,
                    'side_after':parent.container_side,
                    'best_side':archive.container_side,
                    'delta_best_side':max(0.,before-archive.container_side),
                    'accepted':accepted_count>0,
                    'accepted_branch_moves':accepted_count,
                    'stalled_in_row':stalled if branches is None else None,
                    'branch_count':len(branches) if branches is not None else 1,
                    'branch_age':branch_age if branches is not None else 0,
                    'event':event,
                    'valid_children':valid_count,
                    'improving_children':improving_count,
                    'proposed_children':args.children*len(active),
                    'selected_child_index':result['best_index'] if len(active)==1 else None}
            rows.append(record)
            log.write(json.dumps(record)+'\n')
            log.flush()
            render(frames/f'frame_{step:04d}.png',parent,initial_side,step,
                   args.steps,max(0.,before-archive.container_side),accepted_count>0)
            if step==1 or step%50==0 or event:
                print(f'STEP {step}/{args.steps} best={archive.container_side:.12f} '
                      f'phase={record["phase"]} branches={record["branch_count"]} '
                      f'event={event or "-"} proposals={proposal_total} '
                      f'elapsed={time.perf_counter()-start:.1f}s',flush=True)
    # Incomplete branch trial: archive remains the true best, and is
    # guaranteed to be the next run's starting geometry.
    final=archive
    final_policy=archive_policy
    with (output/'trajectory.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (output/'branch_events.json').write_text(json.dumps(branch_events,indent=2),encoding='utf-8')
    (output/'final_packing.json').write_text(json.dumps({
        'container_side':final.container_side,
        'squares':[asdict(x) for x in final.squares],
        'policy':final_policy,'global_policy':controller.global_policy},indent=2),encoding='utf-8')
    summary={'experiment':'single_lineage_adaptive_branching' if args.branches>1
                      else 'single_lineage_strict_improvement',
             'starting_parent':provenance,'seed':args.seed,'steps':args.steps,
             'children_per_step':args.children,'max_branches':args.branches,
             'stagnation_window':args.stagnation_window,
             'significant_gain':args.significant_gain,
             'branch_generations':args.branch_generations,
             'branch_max_regression':args.branch_max_regression,
             'fps':args.fps,'video_duration_seconds':args.steps/args.fps,
             'starting_side':initial_side,'best_side':final.container_side,
             'total_gain':initial_side-final.container_side,
             'accepted_steps':sum(x['accepted'] for x in rows),
             'stalled_steps':sum(not x['accepted'] for x in rows),
             'valid_children':valid_total,'improving_children':improving_total,
             'proposals':proposal_total,'branch_events':branch_events,
             'raw_geometry_checks':gate.raw,'compression_geometry_checks':gate.comp,
             'video_file':'lineage.mp4' if not args.no_video else None,
             'final_geometry_valid':validate_packing(final,tolerance=0.0).valid,
             'continuation_limitation':'Prior random generator and adaptive controller statistics are not restored from legacy files.',
             'elapsed_seconds_without_encoding':time.perf_counter()-start}
    summary_file=output/'run_summary.json'
    summary_file.write_text(json.dumps(summary,indent=2),encoding='utf-8')
    if not args.no_video:
        ffmpeg=shutil.which('ffmpeg')
        if ffmpeg is None:
            summary['video_file']=None
            summary['video_error']='ffmpeg not found on PATH'
            summary_file.write_text(json.dumps(summary,indent=2),encoding='utf-8')
            raise RuntimeError('Images and JSON saved, but ffmpeg missing; install with winget install Gyan.FFmpeg.')
        cmd=[ffmpeg,'-hide_banner','-loglevel','error','-y',
             '-framerate',str(args.fps),'-start_number','1',
             '-i',str(frames/'frame_%04d.png'),'-frames:v',str(args.steps),
             '-c:v','libx264','-pix_fmt','yuv420p','-crf','18',
             str(output/'lineage.mp4')]
        try:
            subprocess.run(cmd,check=True)
        except (subprocess.CalledProcessError,OSError) as e:
            summary['video_file']=None
            summary['video_error']=str(e)
            summary_file.write_text(json.dumps(summary,indent=2),encoding='utf-8')
            raise
    print(f'DONE best L={final.container_side:.12f} | output={output}',flush=True)
    return summary

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sources=parser.add_mutually_exclusive_group()
    sources.add_argument('--input',type=Path,help='Previous selected_population_final.json (optional)')
    sources.add_argument('--resume-packing',type=Path,
                         help='Previous single-lineage final_packing.json; restores geometry and parent policy')
    parser.add_argument('--parent-rank',type=int,default=19,
                        help='0=best imported parent, 19=worst among 20 (default 19)')
    parser.add_argument('--squares',type=int,default=12)
    parser.add_argument('--steps',type=int,default=300)
    parser.add_argument('--children',type=int,default=10)
    parser.add_argument('--fps',type=int,default=30)
    parser.add_argument('--branches',type=int,default=1,
                        help='Maximum temporary lineages, 1..floor(children/2); 1 disables branching')
    parser.add_argument('--stagnation-window',type=int,default=100)
    parser.add_argument('--significant-gain',type=float,default=1e-6)
    parser.add_argument('--branch-generations',type=int,default=100)
    parser.add_argument('--branch-max-regression',type=float,default=.15)
    parser.add_argument('--branch-min-distance',type=float,default=1e-5)
    parser.add_argument('--seed',type=int,default=2716)
    parser.add_argument('--cap-margin',type=float,default=.15)
    parser.add_argument('--contact-probability',type=float,default=.70)
    parser.add_argument('--improvement-epsilon',type=float,default=1e-8)
    parser.add_argument('--no-video',action='store_true',
                        help='Useful for tests if ffmpeg is not installed')
    parser.add_argument('--output-dir',default='results/single-lineage-300')
    args=parser.parse_args()
    run(args)


if __name__=='__main__':
    main()
