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


def run(args):
    if args.steps < 1 or args.children < 1 or args.fps < 1:
        raise ValueError('steps, children and fps must be positive')
    if not 0 <= args.contact_probability <= 1:
        raise ValueError('contact-probability must be 0..1')
    output = Path(args.output_dir).expanduser().resolve()
    if output.exists():
        raise FileExistsError(f'Output already exists: {output}')
    parent, inherited_policy, inherited_global, provenance = load_start(args)
    if not validate_packing(parent,tolerance=0.0).valid:
        raise ValueError('Initial packing fails strict geometry validation')
    controller = AdaptiveCreditController()
    if inherited_global is not None:
        controller.global_policy = normalize_policy(inherited_global)
    policy = normalize_policy(inherited_policy) if inherited_policy is not None else controller.new_policy()
    rng = random.Random(args.seed + 7919)
    compressor = CompressionSettings()
    initial_side = parent.container_side
    output.mkdir(parents=True)
    frames = output/'frames'
    frames.mkdir()
    render(output/'initial.png',parent,initial_side,0,args.steps,0.0,False)
    rows = []
    accepted_total = valid_total = improving_total = 0
    stalled = 0
    start = time.perf_counter()
    with GeometryCounter() as gate, (output/'trajectory.jsonl').open('w',encoding='utf-8') as log:
        for step in range(1,args.steps+1):
            before=parent.container_side
            winner = None
            winner_policy = None
            best_gain = 0.0
            best_index = None
            valid_count = improving_count = 0
            modes = ('normal' if stalled < 40 else
                     'precision' if stalled < 80 else
                     'escape' if stalled < 120 else 'diversify')
            for index in range(1,args.children+1):
                raw_before, comp_before = gate.raw, gate.comp
                gate.phase = 'raw'
                cap = parent.container_side + args.cap_margin
                roll = rng.random()
                if modes == 'precision' and roll < .55:
                    raw,meta = propose_micro(parent,rng,cap)
                elif modes in ('escape','diversify') and roll < (.42 if modes=='escape' else .60):
                    raw,meta = (propose_contact_relocate(parent,rng,cap)
                                if rng.random()<args.contact_probability
                                else propose_reconfigure(parent,rng,cap))
                elif modes in ('escape','diversify') and roll < .75:
                    raw,meta = propose_micro(parent,rng,cap)
                else:
                    raw,meta = propose_learned(parent,rng,cap,policy,controller)
                candidate=raw
                compression_gain=0.0
                gate.phase = 'comp'
                if raw is not None:
                    candidate,_=compress_valid(raw,rng,compressor,cap)
                    compression_gain=raw.container_side-candidate.container_side
                raw_checks, comp_checks = gate.raw-raw_before, gate.comp-comp_before
                valid=candidate is not None and validate_packing(candidate,tolerance=0.0).valid
                raw_gain=parent.container_side-raw.container_side if raw is not None else 0.0
                child_policy,_=controller.update(
                    policy,meta,valid,raw_gain,compression_gain,before,
                    raw_checks,comp_checks,global_best_side=before,train=True)
                if valid:
                    valid_count += 1
                    gain = before - candidate.container_side
                    if gain > args.improvement_epsilon:
                        improving_count += 1
                        if gain > best_gain:
                            winner=candidate
                            winner_policy=child_policy
                            best_gain=gain
                            best_index=index
            valid_total += valid_count
            improving_total += improving_count
            accepted = winner is not None
            if accepted:
                parent=winner
                policy=winner_policy
                accepted_total+=1
                stalled=0
            else:
                stalled+=1
            assert validate_packing(parent,tolerance=0.0).valid
            assert parent.container_side <= before + 1e-12
            record={'step':step,'mode':modes,'side_before':before,
                    'side_after':parent.container_side,'delta_side':best_gain,
                    'accepted':accepted,'stalled_in_row':stalled,
                    'valid_children':valid_count,'improving_children':improving_count,
                    'proposed_children':args.children,'selected_child_index':best_index}
            rows.append(record)
            log.write(json.dumps(record)+'\n')
            log.flush()
            render(frames/f'frame_{step:03d}.png',parent,initial_side,
                   step,args.steps,best_gain,accepted)
            if step == 1 or step%10 == 0:
                print(f'STEP {step}/{args.steps} L={parent.container_side:.12f} '
                      f'mode={modes} accepted={accepted_total} elapsed={time.perf_counter()-start:.1f}s',
                      flush=True)
    with (output/'trajectory.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    final = {'container_side':parent.container_side,
             'squares':[asdict(s) for s in parent.squares],
             'policy':policy,'global_policy':controller.global_policy}
    (output/'final_packing.json').write_text(json.dumps(final,indent=2),encoding='utf-8')
    summary = {'experiment':'single_lineage_strict_improvement',
               'starting_parent':provenance,'seed':args.seed,'steps':args.steps,
               'children_per_step':args.children,'fps':args.fps,
               'video_duration_seconds':args.steps/args.fps,
               'starting_side':initial_side,'best_side':parent.container_side,
               'continuation_limitation':('Past RNG and adaptive controller statistics are not included in old final_packing.json; resumed runs preserve geometry and parent policy, but initialize missing global state.' if args.resume_packing else None),
               'total_gain':initial_side-parent.container_side,
               'accepted_steps':accepted_total,'stalled_steps':args.steps-accepted_total,
               'valid_children':valid_total,'improving_children':improving_total,
               'proposals':args.steps*args.children,
               'raw_geometry_checks':gate.raw,'compression_geometry_checks':gate.comp,
               'video_file':'lineage.mp4' if not args.no_video else None,
               'final_geometry_valid':validate_packing(parent,tolerance=0.0).valid,
               'elapsed_seconds_without_encoding':time.perf_counter()-start}
    summary_file=output/'run_summary.json'
    summary_file.write_text(json.dumps(summary,indent=2),encoding='utf-8')
    if not args.no_video:
        ffmpeg=shutil.which('ffmpeg')
        if ffmpeg is None:
            summary['video_file']=None
            summary['video_error']='ffmpeg not found on PATH'
            summary_file.write_text(json.dumps(summary,indent=2),encoding='utf-8')
            raise RuntimeError('Images and JSON saved, but ffmpeg is missing. Install with winget install Gyan.FFmpeg then run ffmpeg manually.')
        cmd=[ffmpeg,'-hide_banner','-loglevel','error','-y',
             '-framerate',str(args.fps),'-start_number','1',
             '-i',str(frames/'frame_%03d.png'),'-frames:v',str(args.steps),
             '-c:v','libx264','-pix_fmt','yuv420p','-crf','18',
             str(output/'lineage.mp4')]
        try:
            subprocess.run(cmd,check=True)
        except (subprocess.CalledProcessError,OSError) as e:
            summary['video_file']=None
            summary['video_error']=str(e)
            summary_file.write_text(json.dumps(summary,indent=2),encoding='utf-8')
            raise
    print(f'DONE L={parent.container_side:.12f} | output={output}',flush=True)
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
