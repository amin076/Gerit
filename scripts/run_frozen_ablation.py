"""Re-run only the frozen-policy arm; preserve previously completed outputs."""
from __future__ import annotations
from pathlib import Path
import sys,json,zipfile,shutil
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.path.insert(0,str(Path(__file__).resolve().parent))
from run_learning_pilot import DEST,OUTPUT_ZIP,ROOT,source_members,run_arm,ACTIONS

src,sha=source_members()
summary,hist=run_arm('frozen',src,sha)
learned=json.loads((DEST/'learned'/'summary.json').read_text())
old=json.loads((DEST/'baseline'/'summary.json').read_text())
learning_history=[json.loads(line) for line in (DEST/'learned'/'generations.jsonl').read_text().splitlines()]
old_history=[json.loads(line) for line in (DEST/'baseline'/'generations.jsonl').read_text().splitlines()]
plt.figure(figsize=(8,4.5))
for data,name in ((learning_history,'Learned policy'),(hist,'Frozen policy (same operators)'),(old_history,'Previous coordinated mutator')):
    plt.plot([r['generation'] for r in data],[r['best_side'] for r in data],label=name)
plt.xlabel('Generation');plt.ylabel('Best side L');plt.title('12 squares: identical initial 100 packings; 2000 child proposals / arm')
plt.legend();plt.tight_layout();plt.savefig(DEST/'comparison.png',dpi=170);plt.close()
report=json.loads((DEST/'comparison_report.json').read_text())
report['frozen']=summary
report['description']='Three arms; same initial 100 individuals, seed, 20 rounds, 90/10 selection. Trained vs frozen use exact same movement families, continuous magnitude sampling and proposal limit; differ only in policy updates. Previous coordinated arm has different operators and geometry-check budgets.'
report['caveat']='One seed only; trained/frozen arms differ in RNG trajectories after policies diverge. Geometric checks vary with acceptance; broad causal claims require many seeds.'
(DEST/'comparison_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
readme=DEST/'README.md'
readme.write_text(readme.read_text()+'\nThird arm: frozen-policy ablation with the **same new continuous proposal operators** and fixed uniform policy probabilities, run for the same population, seed, and child-proposal count.\n',encoding='utf-8')
shutil.copy2(Path(__file__),DEST/'source_code'/'run_frozen_ablation.py')
shutil.copy2(Path(__file__).parent/'run_learning_pilot.py',DEST/'source_code'/'run_learning_pilot.py')
if OUTPUT_ZIP.exists():OUTPUT_ZIP.unlink()
with zipfile.ZipFile(OUTPUT_ZIP,'w',compression=zipfile.ZIP_DEFLATED) as z:
    for path in DEST.rglob('*'):
        if path.is_file():z.write(path,path.relative_to(DEST.parent))
print(json.dumps({'learned_best':learned['best_side_end'],'frozen_best':summary['best_side_end'],'old_baseline_best':old['best_side_end'],'frozen_valid':summary['accepted'],'zip':str(OUTPUT_ZIP)},indent=2))