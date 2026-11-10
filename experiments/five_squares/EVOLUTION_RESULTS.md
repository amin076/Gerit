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
