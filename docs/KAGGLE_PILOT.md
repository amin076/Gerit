# Kaggle 1,000-problem pilot (experimental)

This branch preserves the existing Gerit engines and the existing main branch.

## Build a durable solution bank

From the repository root:

```cmd
py -3 scripts/kaggle_best_registry.py init
py -3 scripts/kaggle_best_registry.py status
```

Do not run `init` twice against an existing registry. Keep a backup copy of
`results/kaggle_baseline/best_registry.json` before large experiments.

## Run a first short experiment

```cmd
py -3 scripts/run_kaggle_screening.py --n 5 --generations 50 --parents 2 --offspring 5 --mode coordinated --report-every 10
py -3 scripts/kaggle_best_registry.py status
```

The command prints a line after each 10 generations and saves the full experiment
in `results/kaggle_screening/`. Valid improvements replace only the corresponding
problem in the persistent registry. No regressions are permitted.

```cmd
py -3 -m unittest tests.test_kaggle_grid_bank tests.test_kaggle_best_registry tests.test_kaggle_screening -v
```

**Limits:** This screening uses the original `gerit.evolution.evolve` engine.
It does NOT yet use the newer 20-parent adaptive historical-branching engine.
Do not interpret `--parents 2` as two-parent crossover: it means a
two-individual population; the selected mutation engine may use a single
parent per offspring. The historical operators must be integrated and tested
separately. The current registry validator uses Gerit's strict SAT geometry
validator, not a separate mathematical proof or third-party geometric audit.
The official Kaggle format and score still require independent confirmation.
No Kaggle submission is performed here.

**Cost caution:** the existing general engine has quadratic pairwise geometry
validation and population distance calculations. Start with small N. Avoid
running this configuration across all 1,000 sizes until scalability is measured.

Every run now starts from the **validated stored champion** as its initial parent. The evolving population and its learned policies are not yet resumed from a previous run; this is not a full evolutionary checkpoint/resume mechanism.

## Recover validated five-square research (before another screening)

The baseline registry may contain only L=3 while earlier local experiments
have a better full packing. Recover real coordinates, not an approximate L:

```cmd
py -3 scripts/import_gerit_history.py --root results --n 5
py -3 scripts/import_gerit_history.py --root results --n 5 --apply
py -3 scripts/kaggle_best_registry.py status
```

If the dry-run finds no valid coordinates, do not use --apply. Check whether
the historical results live elsewhere or under unsupported filenames.
Only `best_result.json`, `best.json`, `run_result.json`,
`final_result.json` and `selected_population_final.json` are scanned.
The importer validates all square coordinates and strict collision/bounds
geometry; it never fabricates a packing from a reported side length.

Once imported, a **new unique seed** in screening starts from the stored
champion. Do not rerun the same experiment identifier because result files
are intentionally not overwritten.

```cmd
py -3 -m unittest tests.test_import_gerit_history tests.test_kaggle_screening -v
```

## Critical branch compatibility finding (2026-11-11)

**Do not replace the specialized five-square evolution with the generic
screening driver.** The original branch
`feature/five-square-corner-center` has substantial later work not present
in this pipeline branch, including:

- `experiments/five_squares/optimizer.py` and its corner-center founder
- `scripts/run_five_square_evolution.py` with genuine generations
- `gerit/packing_geometry_moves.py` (freely rotating pivots)
- `gerit/contact_compaction.py` (joint contact compaction)
- historical-jump revival, broader exploratory side caps and progress metrics

The founder is four corner squares plus the center square; the specialized
rotation of the center must **not** restrict the corner squares in the
evolutionary offspring. The old fixed-corner specialist is legacy-only.
The feature branches have diverged, so a blind cherry-pick or overwrite of
`gerit/evolution.py` would discard important evolution functionality.

Local historical scan on 2026-11-11 found a validated five-square packing
at L=2.707107181187 under
`results/n5-evolution-500-seed2715/run-20261110T090446Z-b4e90aeb/best_result.json`.
This observed record lives on the Windows machine, not in this repository.
Import this full coordinate record into the registry before another five-square
screening:

```cmd
py -3 scripts/import_gerit_history.py --root results --n 5 --apply
py -3 scripts/kaggle_best_registry.py status
```

Next integration must port the registry **into the existing advanced engine**,
not downgrade the advanced engine to this generic two-parent screening driver.
