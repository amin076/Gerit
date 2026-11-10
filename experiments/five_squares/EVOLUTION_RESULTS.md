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
