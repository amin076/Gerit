Five-square true evolution benchmark, 2026-11-10

This study corrects the earlier experiment: the 250-proposal structural search was NOT a genuine Gerit generational run. The new code injects the exact four-corners-plus-center L=3 packing into the existing gerit.evolution.evolve engine, and optionally tests an added structural mutation alongside the original coordinated mutation. Defaults for existing callers are unchanged.

Verified workflow: https://github.com/amin076/Gerit/actions/runs/42784913460

Both treatments: 30 real generations, 10 parents, four proposed births per parent, seed 2715, 1572 candidate evaluations.

Original coordinated Gerit only: final side 2.920767172804236, score 0.30620678896802933, improvement versus grid 0.03543399753184451, 69 accepted children.

Original coordinated Gerit plus specialist structural mutation (35%): final side 2.70710718118655, score 0.2106551359021931, improvement versus grid 0.13098565059768075, 502 accepted children.

The supplied starting packing is L=3. Both treatments improved during initial population generation before formal generation 0, to L=2.9918074057014716. Thus the recorded generation-zero best is less than the user-supplied initial seed L=3. Generation 30 results above were validated independently by the interval SAT test. These are real offspring, selection, and archival generations, not the separate analytic-specialist trial.

Reproduce:

python -m pip install -r requirements.txt
python -m unittest discover -s tests -p test_five_square_evolution.py -v
python scripts/run_five_square_evolution.py --generations 30 --parents 10 --offspring-per-parent 4 --seed 2715 --no-structural --out results/n5-evo-control
python scripts/run_five_square_evolution.py --generations 30 --parents 10 --offspring-per-parent 4 --seed 2715 --structural-probability 0.35 --out results/n5-evo-hybrid

Neither result has been submitted to Kaggle. No historical experiment is overwritten.

## Local 500-generation run (new recommended configuration)

The CLI now defaults to 500 actual Gerit generations, 20 parents and five
offspring proposals per parent. This configuration is for local runs; the
short GitHub CI control experiment remains intentionally short to protect
runner time. **Do not confuse a configured 500-generation run with a
completed 500-generation result**: the final record exists only after
the local command finishes successfully.

On Windows PowerShell, from the existing repository:

    cd C:\Physics\Gerit
    git status --short
    git fetch origin
    git switch --track origin/feature/five-square-corner-center
    py -3 -m pip install -r requirements.txt
    py -3 -m unittest discover -s tests -p test_five_square_evolution.py -v

If the branch already exists locally, use instead:

    git switch feature/five-square-corner-center
    git pull --ff-only

Run the main 500-generation search on the existing evolutionary engine:

    py -3 scripts/run_five_square_evolution.py --generations 500 --parents 20 --offspring-per-parent 5 --seed 2715 --structural-probability 0.35 --image-every 25 --out results/n5-evolution-500-seed2715

For an important control using the same 500-generation budget but without
the specialized new operator (keeps the *original* Gerit coordinated
operator), run in another new directory:

    py -3 scripts/run_five_square_evolution.py --generations 500 --parents 20 --offspring-per-parent 5 --seed 2715 --no-structural --image-every 25 --out results/n5-control-500-seed2715

All generations, births, parent-child ancestry, and full best-square poses
are preserved as JSON/JSONL. Generation images are saved at 0, 25, 50, ...
500 by default. Use --image-every 1 to save 501 images, at a much larger
storage and runtime cost. The engine maintains its established
append-only experiment folder and refuses to overwrite preexisting results.

The resulting run dir structure is:
- results/n5-evolution-500-seed2715/kaggle_evolution_comparison.json
- results/n5-evolution-500-seed2715/run-*/best_result.json
- results/n5-evolution-500-seed2715/run-*/run_summary.json
- results/n5-evolution-500-seed2715/run-*/generations.jsonl
- results/n5-evolution-500-seed2715/run-*/individuals.jsonl
- results/n5-evolution-500-seed2715/run-*/generation_images/

The final independent Kaggle interval check runs only after all generations
finish. This branch is a study, not a replacement for the current main
evolutionary solver, and no Kaggle submission is uploaded automatically.

Since this specialized operator already reaches within approximately
4e-7 of the known mathematical optimal L for N=5, extra generations might
not materially improve the best result. The no-special-operator control
more honestly evaluates whether generic Gerit benefits from longer evolution.

## Live terminal output (added after 500-generation configuration)

The real evolutionary engine now provides a per-generation callback. The
five-square CLI prints on generation zero, every ten generations by default,
and the final generation. Each line reports generation/total, best side,
current N=5 competition score, evaluated candidates, number of valid children,
and elapsed seconds. It uses flush=True for immediate PowerShell output.
The callback does not modify selection, mutations, or competition scoring.

To show output every 20 generations instead:

    py -3 scripts/run_five_square_evolution.py --generations 500 --parents 20 --offspring-per-parent 5 --seed 2715 --structural-probability 0.35 --report-every 20 --image-every 25 --out results/n5-evolution-500-seed2715

For every ten generations (the default), use --report-every 10. Image saving
frequency (--image-every) is independent of progress reporting frequency.
The main 500-generation run must be started on the local machine; the
GitHub workflow intentionally executes short smoke tests only.

## Critical correction: user-requested unrestricted five-square evolution

The four-corners-plus-center arrangement is ONLY the initial geometry.
The old default specialized center operator incorrectly forced the four
outer square angles back to zero every time it ran. It is now OFF by default.
It can be reenabled ONLY with --legacy-center-operator to reproduce the old
biased experiment; do not use that option for genuine exploratory evolution.

Normal default evolution combines Gerit's preexisting coordinated multi-square
mutation (any 2-5 indices freely translate and rotate), and Gerit's existing
reconfiguration and contact-guided structural moves (any square can move).
No square is forced to remain upright and the center is not privileged.

The envelope is permitted to expand to 3.8 during evolutionary exploration,
while the initial supplied seed remains exactly L=3. Valid intermediate
individuals larger than L=3 are allowed and can remain as exploratory parents.
Historical-jump revival is enabled by default: after 30 no-improvement
generations, every 20th generation can reintroduce one actual old parent.
Both the original founders and a rolling historic archive are retained.
Parent lineage and the archive source generation are logged for auditing.
This is distinct from preserving only the historical best score.

The console reports every 10 generations by default (or --report-every 20),
including the number of rotated parents, true geometrically different parent
layouts, maximum current population side, cumulative historical revivals,
and objective score. These metrics help distinguish genuine exploration from
mere reproduction of the known N=5 answer.

RUN ON WINDOWS POWERSHELL (use a fresh output folder):

    cd C:\Physics\Gerit
    git fetch origin
    git switch feature/five-square-corner-center
    git pull --ff-only
    py -3 -m unittest discover -s tests -p test_five_square_evolution.py -v
    py -3 scripts/run_five_square_evolution.py --generations 500 --parents 20 --offspring-per-parent 5 --seed 2715 --exploration-side-cap 3.8 --historical-jump-every 20 --historical-stagnation-after 30 --report-every 10 --image-every 25 --out results/n5-free-historic-500-seed2715

This is a new prospective experiment, not a completed 500-generation result.
The old 500-generation output cannot be used as proof of unrestricted movement.

## 2026-11-10: Geometry-only corrective experiment, verified

The **evolutionary engine was not changed for this correction**.
A separate general geometry operator was added in
`gerit/packing_geometry_moves.py`: `propose_pivot_release`.
It selects a square by centrality/randomness, rotates that pivot,
simultaneously moves the other squares radially inward or outward,
and optionally rotates each other square independently. Each whole
candidate is validated by zero-tolerance SAT. It is generic for N>=2;
it contains no special constant for N=5, no precomputed arrangement,
and no mathematically optimal solution injection.

The N=5 experiment script selects this geometric operator in 60%
of its optional structural proposals and retains general reconfigure
and contact-guided relocation for the rest. Existing coordinated
reproduction, selection, historical retrieval and scoring are unchanged.

Independent GitHub Actions verification:
https://github.com/amin076/Gerit/actions/runs/42794029015

- Geometry-only unit tests: 3 passed for both jobs
- 10 genuine generations: L=2.768677477322183; SAT certified
- 20 genuine generations: L=2.768677477322183; SAT certified
- 10-gen score (N5): 0.2381902094
- 20-gen score (N5): 0.2381902094
- Population: 20, 5 offspring per parent
- 20/20 parents had at least one rotated square by generations 10 and 20
- Archived historical revival count: 2 by generation 10, 4 by generation 20
- The best did not improve from generation 10 to generation 20; this
  is not a guarantee that 500 generations will improve further.

To reproduce the 500-generation run in Windows PowerShell, update the
existing branch and run with a NEW output directory:

```powershell
cd C:\Physics\Gerit
git status --short
git fetch origin
git switch feature/five-square-corner-center
git pull --ff-only
py -3 -m unittest discover -s tests -p test_packing_geometry_moves.py -v
py -3 scripts/run_five_square_evolution.py --generations 500 --parents 20 --offspring-per-parent 5 --seed 2715 --structural-probability 0.35 --exploration-side-cap 3.8 --historical-jump-every 20 --historical-stagnation-after 30 --report-every 10 --image-every 25 --out results/n5-geometry-free-500-v2
```

The command prints progress every 10 generations, retains every
generation/individual/selection log, and saves population images every
25 generations. Do not reuse an existing output directory.

## New 2000-generation continuation seeded from user's REAL local 500-generation best

Input is saved at `experiments/five_squares/seed_from_local_500.json`.
It contains exactly the five square positions and angles from uploaded
`best_result(1).json` (recorded `best.side=2.7743606307960853`).

This is a NEW 2000-generation run seeded from the saved BEST GEOMETRY,
NOT an exact restart of all 20 parent genomes, prior RNG state, branch
history, historical archive or controller statistics. That information is
not present in the one-best geometry file; the current evolve() interface
accepts one initial packing and generates a fresh population from it.
No alteration of the generic evolution engine has been made to support
this continuation.

### Precise interpretation of existing branch settings

- Concurrent evolutionary populations (true parallel branches): **ONE**.
- Current parent population: 20 individuals, NOT 20 independent branches.
- Selection is 75% fitness (15 parent survivor slots) and 25% diversity
  (5 survivor slots). These are parent-selection quotas, not historical
  and normal branch counts.
- Each generation proposes 20 x 5 = 100 offspring.
- Specialist free geometry contributes 35% of offspring attempts, where
  the geometric operator itself chooses pivot-release 60%, general
  reconfiguration 20% and contact relocation 20%.
- Historical archive stores 150 most recent selected genomes in addition
  to original founders and selects AT MOST ONE historical parent when
  enabled. With `--historical-jump-every 20` and
  `--historical-stagnation-after 30`, it attempts one revival on
  the 20-generation checkpoints when stalled for >=30 generations.
- There is NO automatic second/third/fourth concurrent search branch,
  NO scheduled branch birth or reduction, and NO historical-vs-normal
  branch allocation in this five-square evolution entry point.
  Do NOT misreport historical revivals as branch count.
- The user-requested gradual multibranch creation/pruning system is a
  different research workflow and is NOT implemented by this CLI.
  Main selection, survival and historical behavior remain unchanged.

### Run in Windows PowerShell

    cd C:\Physics\Gerit
    git status --short
    git fetch origin
    git switch feature/five-square-corner-center
    git pull --ff-only
    py -3 -m unittest discover -s tests -p test_five_square_evolution.py -v

Then run with a fresh output directory:

    py -3 scripts/run_five_square_evolution.py --initial-best-file experiments/five_squares/seed_from_local_500.json --generations 2000 --parents 20 --offspring-per-parent 5 --seed 2715 --structural-probability 0.35 --exploration-side-cap 3.8 --historical-jump-every 20 --historical-stagnation-after 30 --report-every 10 --image-every 25 --out results/n5-continued-from-500-for-2000

This will print current best, evaluations, historical revivals, actual
geometric diversity, and rotated-parent counts every ten generations.
The run refuses to overwrite its output directory. A successful run
will produce an independently verified final packing and complete
new evolution logs. The first generation is numbered 0 in the new
experiment; it is not labeled global generation 500 because the old
stochastic population wasn't actually restored.

To start from a downloaded local `best_result.json` directly instead,
replace the --initial-best-file argument with the file path.

## Contact-aware multi-square geometric compaction: A/B-verified

Code: `gerit/contact_compaction.py`. No changes to the evolutionary
engine for this study. It chooses contact-adjacent and boundary-active
square groups, perturbs centers AND rotations jointly at three
decreasing scales, enforces zero-tolerance SAT validation, and
retains only non-worsening geometries. All squares can rotate.

The study starts from user's exact 2000-generation result:
`experiments/five_squares/seed_from_local_2000.json`,
L = 2.7470414077646637. The CLI option
`--contact-compaction-probability 0.60` dedicates 60% of the
*structural proposal calls* to the new local compactor. Structural
proposal probability itself stays 0.35; the other 65% calls use
Gerit's unchanged coordinated mutation, and within remaining
structural calls normal existing geometry operators still run.

Verified GitHub Actions workflow:
https://github.com/amin076/Gerit/actions/runs/42801428624

| True generations | No compaction (A) | With compaction (B) |
| --- | --- | --- |
| 10 | 2.7470414077646637 | 2.713674530594033 |
| 20 | 2.7470414077646637 | 2.7112254606484227 |

All four jobs succeeded, including four dedicated unit tests in
each job and independently certified interval SAT output validation.
This is a promising early test on one random seed, NOT a multi-seed
proof of general effectiveness.

Recommended Windows local 500-generation followup:
```powershell
cd C:\Physics\Gerit
git fetch origin
git switch feature/five-square-corner-center
git pull --ff-only
py -3 -m unittest discover -s tests -p test_contact_compaction.py -v
py -3 scripts/run_five_square_evolution.py --initial-best-file experiments/five_squares/seed_from_local_2000.json --generations 500 --parents 20 --offspring-per-parent 5 --seed 2715 --structural-probability 0.35 --contact-compaction-probability 0.60 --exploration-side-cap 3.8 --historical-jump-every 20 --historical-stagnation-after 30 --report-every 10 --image-every 25 --out results/n5-contact-from-2000-500
```

Existing original results are preserved. The new search resets RNG,
selected population, and historical archive, but injects the exact
best known user geometry. Output folder must not already exist.

## Micro-scale near-contact geometry: multi-seed study from user L=2.70803534098831

This is an **opt-in geometry-only** change, NOT an adjustment of
parent selection, population scheduling or historical jump logic.

- Latest saved checkpoint: `experiments/five_squares/seed_from_local_contact_500.json`
- Old geometric scales: `(0.040, 0.013, 0.003)`
- New micro scales: `(0.002, 0.00035, 0.000035)`
- CLI flag: `--fine-contact-scales` (old behavior remains the default).
- Both branches keep 60% of structural candidates assigned to
  contact compaction; structural probability remains 35%.
- Random seeds: 2715, 2716, 2717.
- A/B generation budgets: 30 each, 6 real evolutionary runs.
- Every run independently checks zero-tolerance geometry and
  final interval SAT. The previous best L must not be lost.

Workflow: https://github.com/amin076/Gerit/actions/runs/42813762838

To run 500 local generations with the updated geometry after
the smoke tests finish, use PowerShell:

```powershell
cd C:\Physics\Gerit
git fetch origin
git switch feature/five-square-corner-center
git pull --ff-only
py -3 -m unittest discover -s tests -p test_contact_compaction.py -v
py -3 scripts/run_five_square_evolution.py --initial-best-file experiments/five_squares/seed_from_local_contact_500.json --generations 500 --parents 20 --offspring-per-parent 5 --seed 2715 --structural-probability 0.35 --contact-compaction-probability 0.60 --fine-contact-scales --exploration-side-cap 3.8 --historical-jump-every 20 --historical-stagnation-after 30 --report-every 10 --image-every 25 --out results/n5-contact-fine-from-l2708035-500
```

The reported 500-generation result is a checkpoint, not a guarantee
that additional micro-scale generations will improve it. Preserve
the previous run folders and use a fresh output path.
