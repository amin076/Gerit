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
