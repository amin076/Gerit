# Gerit advanced evolution + 1,000-solution archive

This feature branch was created FROM `feature/five-square-corner-center`,
NOT from the obsolete generic engine. It preserves historical revival,
independent geometrical founders, freely rotating all squares, contact
compaction, structural reconfiguration, and true two-parent quadrant crossover.

The registry is **an archive of verified winners**, not a fitness target and
not a mandatory initial parent. Default `--start fresh` deliberately begins
independently of stored champions. This prevents limiting novel search.

## Windows commands

```cmd
cd C:\Physics\Gerit
git status
git fetch origin
git switch -c feature/gerit-1000-integrated --track origin/feature/gerit-1000-integrated
py -3 -m pip install -r requirements.txt
py -3 -m unittest tests.test_kaggle_grid_bank tests.test_kaggle_best_registry tests.test_import_gerit_history tests.test_kaggle_advanced_bank -v
```

Existing `results/kaggle_baseline/best_registry.json` persists across branch
switches; **DO NOT rerun registry init** if it already exists.

First import previously validated local N=5 results:

```cmd
py -3 scripts/import_gerit_history.py --root results --n 5
py -3 scripts/import_gerit_history.py --root results --n 5 --apply
py -3 scripts/kaggle_best_registry.py status
```

Then **move beyond N=5**: launch four small 50-generation experiments.

```cmd
py -3 scripts/run_kaggle_advanced_batch.py --counts 6 7 8 10 --generations 50 --parents 2 --offspring 5 --start fresh --founder auto --report-every 10
py -3 scripts/kaggle_best_registry.py status
```

No expensive all-1000 sweep is started automatically. Confirm runtime and
valid offspring rate at small N first. Large-N uses quadratic pair checks
and requires a dedicated performance review.

### Initialization controls

- `--start fresh`: default. Independent founder from Gerit's existing
  geometric operators; ignores registry as an initial parent.
- `--start stored`: explicitly resume from the registry's validated best
  geometry; does not restore an entire population or controller state.
- `--start mixed`: inject both independent founder and stored champion,
  only when requested.

For N=5, `--founder auto` and `corner-center` use the EXISTING
`best_inward_for_angle(pi/4)` four-corner/rotated-center founder.
For other N, `auto` uses existing symmetry/corner-first operators.
After initialization all square angles are unrestricted. Historical
jump and structural mutation remain active. Two-parent crossover
uses the existing `multi_parent_quadrant_crossover`; its probability
defaults to 0.20, structural proposals default to 0.35.

Example alternative fresh N=5 experiment (not necessary for batch):

```cmd
py -3 scripts/run_kaggle_advanced_batch.py --counts 5 --generations 50 --parents 2 --start fresh --founder corner-center --seed 20261115
```

Each N writes a separate run directory and independent validation report.
A strictly better and independently interval-validated result updates the
registry immediately through the engine's optional best-packing callback,
including intermediate generations (not only the end of the run). A worse valid result remains as an experiment record,
not as a replacement. Interrupted batches preserve completed N entries and
older bank solutions. If restarting, use only the remaining N with a fresh
output identity or a different seed.

### What this does NOT do

- Does not merge obsolete `gerit/evolution.py` on top of the advanced engine.
- Does not remove earlier experiments or force historic records into populations.
- Does not prove a global optimum or auto-submit to Kaggle.
- Does not make 1000 simultaneous evolutionary populations.
- Does not certify good performance for hundreds of squares.
- Does not restore historical archive/controller RNG state from a single best.
- Does not run genetic experiments automatically on the user's Windows PC.

The command and tests should be executed on the target Windows environment
before declaring the integration verified.

## 2026-11-11 screening diagnosis and diverse-founder change

Observed local 50-generation screening:
- N=6: L=3, zero registry improvements
- N=7: L=3, zero registry improvements
- N=8: L=3, zero registry improvements
- N=10: L=4, zero registry improvements
- Baseline registry after importing historical N=5: 28.806684265953.

A 2-parent population initialized from one seed can collapse back to grid
geometry even though free rotations and historical jumps are enabled.
The fresh mode now attempts a *second independent valid founder* from the
pre-existing Gerit geometry operator bank, selecting a packing with a
different structural signature. This is optional (disable with
`--no-diverse-founders`). It is NOT a guarantee of better fitness and
does not change survivor quotas, crossover, archive or geometry validators.

To check the new initializer and compare against the already completed runs:

```cmd
py -3 -m unittest tests.test_kaggle_advanced_bank -v
py -3 scripts/run_kaggle_advanced_batch.py --counts 6 7 8 10 --generations 50 --parents 2 --offspring 5 --seed 20261113 --start fresh --founder auto --report-every 10
py -3 scripts/kaggle_best_registry.py status
```

Every experimental run has a unique seed-based directory. The registry
continues to preserve previous winners if the new experiments fail.
To explore more counts in parallel-sized *sequential* tasks, change
`--counts`; do not assume any given N has a sub-grid solution.
Do not repeat five-square runs just because the score hasn't changed.
