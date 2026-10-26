"""Independent post-run audit of all nine fixed-budget Gerit experiment arms."""
import json,hashlib,zipfile,math
from pathlib import Path
from gerit.geometry import Square,Packing,square_vertices,validate_packing
from shapely.geometry import Polygon

ROOT=Path('/mnt/data/Gerit_reward_v2_benchmark')
SOURCE=Path('/mnt/data/Gerit_round13_12squares_100_generations.zip')
SEEDS=[2601,2602,2603]
ARMS=['v2_credit','frozen','v1_credit']

def run():
    with zipfile.ZipFile(SOURCE) as z:
        name=next(n for n in z.namelist() if n.endswith('selected_population_final.json'))
        b=z.read(name)
        orig=json.loads(b)['selected_members']
    old_ids={int(m['individual_id']) for m in orig}
    sha=hashlib.sha256(b).hexdigest()
    results=[]
    for seed in SEEDS:
        for arm in ARMS:
            folder=ROOT/f'seed_{seed}'/arm
            summary=json.loads((folder/'summary.json').read_text())
            assert summary['source_sha256']==sha
            assert summary['validation_checks_used']==12000
            assert summary['raw_geometry_checks']+summary['compression_geometry_checks']==12000
            individuals=[json.loads(x) for x in (folder/'individuals.jsonl').read_text().splitlines()]
            assert len(individuals)==100+summary['births_completed']
            assert len({x['id'] for x in individuals})==len(individuals)
            observed=set()
            valid=0;invalid=0
            for row in individuals:
                if row['generation']==0:
                    assert row['id'] in old_ids
                else:
                    assert len(row['parent_ids'])==1 and row['parent_ids'][0] in observed
                observed.add(row['id'])
                if not row['valid']:
                    invalid+=1;continue
                valid+=1
                sq=tuple(Square(**s) for s in row['squares'])
                p=Packing(sq,row['L'])
                assert len(sq)==12 and validate_packing(p,tolerance=0.0).valid,(arm,seed,row['id'])
            assert valid==100+summary['valid_children']
            assert invalid==summary['invalid_children']
            hist=[json.loads(x) for x in (folder/'generations.jsonl').read_text().splitlines()]
            assert hist[0]['generation']==0
            assert all(b['best_side']<=a['best_side']+1e-11 for a,b in zip(hist,hist[1:]))
            assert hist[-1]['geometry_checks']==12000
            assert hist[-1]['best_side']==summary['final_best_side']
            selected=json.loads((folder/'selected_population_final.json').read_text())['selected_members']
            assert len(selected)==100
            assert all(m['individual_id'] in observed for m in selected)
            assert abs(min(m['container_side'] for m in selected)-summary['final_best_side'])<1e-11
            # Independent polygon check on all final individuals, not just best.
            max_inter=0.0;max_boundary=0.0
            for m in selected:
                sq=[Square(**s) for s in m['squares']]
                side=m['container_side']
                polys=[Polygon(square_vertices(s)) for s in sq]
                for poly in polys:
                    xmin,ymin,xmax,ymax=poly.bounds
                    max_boundary=max(max_boundary,-xmin,-ymin,xmax-side,ymax-side)
                for i in range(12):
                    for j in range(i+1,12):
                        max_inter=max(max_inter,polys[i].intersection(polys[j]).area)
            assert max_inter<1e-11 and max_boundary<1e-9
            results.append({'seed':seed,'arm':arm,'geometry_checks':12000,
                            'complete_births':summary['births_completed'],
                            'final_side':summary['final_best_side'],
                            'all_valid_individuals':valid,
                            'final_selected_count':len(selected),
                            'max_final_polygon_overlap':max_inter,
                            'max_boundary_error':max_boundary})
    result={'status':'passed','audited_arms':len(results),'initial_sha256':sha,
            'exact_geometry_budget_each':12000,'audited_selected_individuals':len(results)*100,
            'runs':results}
    (ROOT/'verification.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({'status':result['status'],'arms':len(results),'selected_polygons':900},indent=2))
    return result

if __name__=='__main__':run()