# Symmetry geometry operators and multi-parent Gerit experiment

The genetic engine is still `gerit.evolution.evolve`: original survivor
selection (75% fitness / 25% geometric diversity), population, branching,
and historical archive are unchanged.

## Modules and contracts

- `gerit/symmetry_operators.py` contains reusable, testable, strictly validated
  geometry **seed** generators and **mutation** functions. None chooses parents
  or determines who survives.
- `GeometryOperator(name,description,generate)` is the registry interface.
  Available generation families: `fourfold` (90-degree rotation),
  `diagonal_pairs` (180-degree opposing diagonal), `horizontal`,
  `vertical`, `corner_first`, `four_corner_clusters`,
  `random_sparse`. A regular `grid` is preserved as control.
- `propose_symmetry_group_move(parent,rng,cap)` generates a symmetry-paired
  offspring from an existing parent. Full continuous rotation freedom is
  preserved by the ordinary coordinated operator.
- `multi_parent_quadrant_crossover(first,second,rng,cap)` proposes a genuine
  two-parent crossover, transferring a matching quadrant. Invalid children
  are rejected by SAT; **both real parent IDs are recorded**.
- `evolve(..., initial_seeds=(), multi_parent_mutator=None,
  multi_parent_probability=0.0)` has opt-in hooks. Its old default behaviour
  and previous random-number consumption are retained when these options are
  omitted.
- `scripts/run_symmetry_three_counts.py` executes 17, 18, 19 **sequentially**;
  tracks their independently validated best, the family of each initial
  geometry, experimental score, generations, and elapsed seconds.

The 17-square four-corner-clusters construction is a general
`4*m*m+1` template (for m>=2). It does not store a known answer:
four m×m blocks and one rotated central square are compacted by a
binary search that asks the strict collision validator whether an
inset is geometrically feasible. Starting N=17 best at generation zero
is about **4.707146783072**, beating the plain grid L=5 but still worse
than reference L=4.675530093605. This is an **engineered initial
geometry**, not a new evolutionary record.

For N=18/19, the current seeds remain at L=5 in the short ten-generation
CI smoke tests. The goal is to build and measure additional structural
operators, not to claim they solve the known packing benchmarks.

## Windows CMD

```bat
cd C:\Physics\Gerit
git switch feature/five-square-corner-center
git pull --ff-only
py -3 -m unittest discover -s tests -p test_symmetry_operators.py -v
py -3 -u scripts/run_symmetry_three_counts.py --generations 10 --report-every 1 --out-root results/symmetry-3x10
```

Then, after inspecting output:

```bat
py -3 -u scripts/run_symmetry_three_counts.py --generations 50 --report-every 10 --out-root results/symmetry-3x50
```

For a 500-generation comparison with the former sequential experiment:

```bat
py -3 -u scripts/run_symmetry_three_counts.py --generations 500 --report-every 20 --image-every 50 --out-root results/symmetry-3x500
```

Each output root must be new. Individual puzzle reports and poses are
saved under `n17`, `n18`, `n19`. Gerit lineage, all proposals,
selection and historical jump logs remain in nested `run-*` folders.

`GEN 0/...` may already improve from the prior L=5: this is a seed
gain and **not** an evolutionary-generation gain. Record both metrics.

## CI verification

`tests/test_symmetry_operators.py` verifies strict validity, the
N17 compacted seed, distinct seeded founders, two-parent ancestry and
the unchanged legacy entrypoint. The GitHub Actions workflow
`.github/workflows/gerit-symmetry-multiparent.yml` runs regression
tests and sequential 10-generation end-to-end tests with independent
interval validation.
