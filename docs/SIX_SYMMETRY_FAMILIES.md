# Gerit: six symmetry families and method provenance

This implementation **does not replace** existing Gerit evolution, four-corner
45-degree geometry, or the 1,000-answer registry.

## Six standalone experiments

| Family | Script | Constraint / move |
| --- | --- | --- |
| Fourfold | `scripts/run_fourfold_family.py` | All matched quarter-turn (90 degree) orbits are moved together |
| Left/right | `scripts/run_vertical_reflection_family.py` | Mirrored horizontal displacements across vertical axis |
| Top/bottom | `scripts/run_horizontal_reflection_family.py` | Mirrored vertical displacements across horizontal axis |
| Twofold | `scripts/run_diagonal_pairs_family.py` | Paired 180-degree rotational displacement |
| Corner clusters | `scripts/run_corner_cluster_family.py` | Corner-priority groups, optional central motif when supported |
| Three plus one | `scripts/run_three_plus_one_family.py` | Three linked corner motions, fourth corner may depart independently |

These are **heuristic search families** and some irregular N cannot have
exact full symmetry. Orbits are only mutated when the complete symmetry
orbit is present. The corner and three-plus-one families are
partial-symmetry explorations, not proofs of exact full invariance.
Every candidate uses rigid unit squares and strict SAT validation.
Only a candidate independently certified by interval SAT, *and* better
than the registry winner, is allowed to update the bank.

The new local refiner does not use Gerit's full advanced historical-jump
population search; it is an independent **within-family** geometric search.
The advanced evolutionary engine remains available for the next stage.

## Method ledger and audit trail

Every finished family run writes:
- `results/kaggle_method_ledger.jsonl`: append-only event with N, seed,
  algorithm, family, exact script path, iteration settings, previous and
  candidate side lengths, validity and acceptance status.
- `results/kaggle_family_reports/family-...json`: all square coordinates,
  score comparisons, interval-validation reason, and provenance.
- `results/kaggle_family_reports/method_summary.csv`: per-family totals.

Existing registry winners already store source, operator, experiment ID and
validation method. Import **only known information**, leaving absent
historical seeds unknown, using:

```cmd
py -3 scripts/backfill_kaggle_method_ledger.py
```

This backfill is idempotent for historical winners and never changes the
registry. Never fabricate provenance from an older winner.

## How to run each family in the requested order

```cmd
git pull --ff-only
py -3 -m unittest tests.test_symmetry_family_runner -v
py -3 scripts/backfill_kaggle_method_ledger.py
py -3 scripts/run_fourfold_family.py --counts 5 8 10 11 12 14 17 18 19 20 --iterations 200 --seed 20261113 --apply
py -3 scripts/run_vertical_reflection_family.py --counts 5 8 10 11 12 14 17 18 19 20 --iterations 200 --seed 20261113 --apply
py -3 scripts/run_horizontal_reflection_family.py --counts 5 8 10 11 12 14 17 18 19 20 --iterations 200 --seed 20261113 --apply
py -3 scripts/run_diagonal_pairs_family.py --counts 5 8 10 11 12 14 17 18 19 20 --iterations 200 --seed 20261113 --apply
py -3 scripts/run_corner_cluster_family.py --counts 5 8 10 11 12 14 17 18 19 20 --iterations 200 --seed 20261113 --apply
py -3 scripts/run_three_plus_one_family.py --counts 5 8 10 11 12 14 17 18 19 20 --iterations 200 --seed 20261113 --apply
py -3 scripts/kaggle_best_registry.py status
```

For a broader new range use `--counts 21 22 23 24 26 27 28 29 30 31 32`.
Use different `--seed` to perform independent repeats; completed experiment
reports are intentionally never overwritten. Do not run multiple processes
concurrently with `--apply`: registry updates are single-process only.

The separate `Gerit six symmetry families` GitHub Actions workflow
executes all six scripts sequentially, 80 iterations on ten counts per family,
with a disposable registry and uploaded reports. This does **not** alter the
user's local registry. Archive contents are available as workflow artifacts.

Unlike the center-45 exact family, these six structured mutators have not yet
demonstrated improvement on any given N; read actual reports instead of
assuming gains.
