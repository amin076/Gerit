# Next Gerit sieve: insert one square into unused space

The previous L-frame is defined for ANY verified source, but yielded
competitive results only on the chain N=k*k+1 in the current 1,000-problem
bank. It helped 29 destination counts, producing 30 winners including the
original N=5. This DOES NOT make L-frame special-purpose code.

## Distinct geometric approach: gap insertion

Instead of adding a full L-frame, this family tries to place **one**
extra unit square into the existing geometric arrangement, at rotations
0, 15, 30 and 45 degrees, while holding all inherited square positions
fixed. Positions include geometric pocket/lattice points and randomized
probes. It can potentially affect any N->N+1, not just square-plus-one
counts. Because it is a heuristic, no improvement is guaranteed and a
failed placement does not prove optimality.

`gerit/gap_insert_geometry.py` generates candidate positions and rejects
overlaps using strict SAT. `scripts/run_gap_insertion_screen.py` screens
the entire bank, starting only from already improved answers by default
(to save computation), allows a successful new answer to become a source
for the following N, validates every competitive candidate with the
independent high-precision checker, and only then offers a winning answer
to the single-process registry. Every completed candidate is logged with
source, target, method and seed.

## Commands in Windows CMD

```cmd
cd C:\Physics\Gerit
git pull --ff-only
py -3 -m unittest tests.test_gap_insertion_screen -v
py -3 scripts/run_gap_insertion_screen.py --samples 300 --report results/kaggle_gap_insertion/dryrun.json
```

Read `target_ns`, `accepted_count`, `initial_score` and `final_score`
from the JSON report before writing the registry.

If the dry-run shows real improvements and independent validation passes,
execute:

```cmd
py -3 scripts/run_gap_insertion_screen.py --samples 300 --apply --report results/kaggle_gap_insertion/applied.json
py -3 scripts/kaggle_best_registry.py status
```

For a distinct repeat use a new seed and report path:

```cmd
py -3 scripts/run_gap_insertion_screen.py --samples 1000 --seed 20261118 --report results/kaggle_gap_insertion/dryrun-seed2.json
```

The `--all-sources` flag also tests unimproved geometries (can be much
slower). Reports are never overwritten; choose a new file name for each
run. The automated workflow `Gerit gap insertion geometric screen` is
an independent screening experiment against a DISPOSABLE archive which
includes the previous 30 geometries. It never mutates the local registry.
