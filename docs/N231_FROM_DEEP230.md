# N231: grow from verified deep N230 and continue packing, not just <16

The user's current locally certified 230-square solution after 900
generations was reported at L=15.946108063542, but its coordinates
are in the user's **local experiment folder**, not in this repository.
For scientific validity, do not silently substitute the 16x16 grid
as the founder.

The dedicated 231 experiment uses the existing continuous
all-square placement/rotation optimizer with stronger high-penalty
repair, and saves an independently SAT-certified 231 candidate. It
then passes **that same candidate**, without requiring registration,
to the deep fixed-N optimizer for a fresh 900-generation compression.

All experiment results and checkpoints are append-only. Without
`--apply` the original 1000-puzzle registry is unchanged.

## Windows CMD

```cmd
cd C:\Physics\Gerit
git switch feature/gerit-1000-integrated
git pull --ff-only
py -3 -m unittest tests.test_n231_pipeline -v
```

### A. N231 growth using the independently certified N230 deep winner

```cmd
py -3 scripts/run_elastic_repair.py --n 231 --source-file results/kaggle_deep/n230_g900_s2300/best_valid.json --attempts 96 --iterations 600 --seed 105 --report results/kaggle_elastic_growth/n231_from_deep230_s105.json --checkpoint results/kaggle_elastic_growth/n231_from_deep230_s105_nearest.npz --best-file results/kaggle_elastic_growth/n231_from_deep230_s105_best.json
```

Look for `CERTIFIED attempt=...` and the `best-file`
being created. If unsuccessful try a *different seed* and fresh
output filenames rather than overwriting archived experiments.

The source file is independent of whether the N230 dry-run winner
has already been registered. The source is independently validated
before use. The target cap starts below 16.

### B. Deep compression after the first N231 certified candidate

If and only if the `best-file` exists:

```cmd
py -3 scripts/run_deep_elastic.py --n 231 --candidate-file results/kaggle_elastic_growth/n231_from_deep230_s105_best.json --generations 900 --iterations 180 --seed 2310 --log-every 10 --shrink-max 0.035 --output-dir results/kaggle_deep/n231_g900_s2310
```

This starts from the independently certified N231 growth winner
without first modifying the best archive. It prints checkpoints
every 10 generations. The best certified packing is preserved as
`results/kaggle_deep/n231_g900_s2310/best_valid.json`.

After reviewing, register the *verified* result without repeating
900 generations:

```cmd
py -3 scripts/run_deep_elastic.py --n 231 --generations 1 --iterations 80 --seed 2311 --candidate-file results/kaggle_deep/n231_g900_s2310/best_valid.json --output-dir results/kaggle_deep/n231_register_s2311 --apply
py -3 scripts/kaggle_best_registry.py status
```

Then optionally propagate the independently certified N231 solution
down to N230..227:

```cmd
py -3 scripts/run_downward_propagation.py --source-n 231 --min-n 227 --report results/kaggle_deep/downward231_dryrun.json
```

Only apply downward propagation after inspecting the dry run; use a
fresh report path for `--apply`.

## Caveats

- A 96-start search can still produce zero certified packings.
- `certified=True` refers to interval-verified geometry. It does not
  prove global optimality.
- The GitHub CI tests validate integration using small synthetic
  puzzles. They cannot run from the user's local 230 packing
  without that file being uploaded or committed.
- Do not have two commands writing the registry simultaneously.
