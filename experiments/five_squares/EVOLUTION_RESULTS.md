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
