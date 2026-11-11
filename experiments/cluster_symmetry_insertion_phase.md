# Cluster geometry phase: three independently testable operators

This phase builds on `gerit/symmetry_operators.py`. The evolutionary engine,
fitness/diversity survivor selection, archived revival, and multi-parent
crossover remain unchanged.

## New geometry-only functions

**Module**: `gerit/cluster_geometry_operators.py`

- `propose_cluster_compaction(parent,rng,side_cap,attempts=70)`:
  selects a near-neighbour group or connected component, translates and
  rotates it as a block, and permits small individual relaxation.
- `propose_symmetry_break(parent,rng,side_cap,attempts=70)`:
  releases a quadrant (or a subset) independently of its mirrored members.
- `propose_incremental_insertion(source,rng,target_n,side_cap,attempts=350)`:
  builds a larger-N packing from smaller-N geometry using uniform relaxation
  and insertion proposals. It is a **founder constructor**, not a same-N
  evolutionary mutation, and it can return None.
- `build_incremental_founder(n,rng,cap,sources=...,attempts=260)`:
  tries independently generated smaller-N packings as insertion sources.

Each returns a strictly validated `Packing` or `None`.
No hardcoded best-known coordinates, target length, or N-specific lookup
are used. The search may fail, and this must not be confused with an
invalid candidate. Square count is preserved by the two mutation
operators; insertion changes it intentionally.

## Experiment routing

`scripts/run_symmetry_three_counts.py` adds optional operator controls:

- `--cluster-share 0.30`
- `--break-share 0.25`
- `--symmetry-mutation-share 0.20`
- `--insertion-attempts 75`

These shares describe fractions **within the structural-operator branch**;
other offspring still use two-parent crossover or Gerit's standard
coordinated mutation. The total must be at most one; remaining structural
proposals use previous generic geometric methods.

The summary files include `operator_stats` with attempted, valid,
and parent-improving proposals; this is separate from global best gains.
Extra insertion-derived founders are marked by name in `founder_names`.
Generation-zero seed gains are explicitly separate from evolutionary
gains.

## Windows CMD: recommended 50 generations

```bat
cd C:\Physics\Gerit
git switch feature/five-square-corner-center
git pull --ff-only
py -3 -m unittest discover -s tests -p test_cluster_geometry_operators.py -v
py -3 -u scripts/run_symmetry_three_counts.py --generations 50 --parents 20 --offspring-per-parent 5 --report-every 10 --image-every 10 --out-root results/symmetry-cluster-3x50
```

Counts run sequentially: N=17, N=18, N=19.
The previous `results/symmetry-3x50` remains untouched.

If and only if the 50-generation reports show meaningful improvements,
the same settings may be tested at 500 generations using a new output
directory. Strict geometry and independently certified validation remain
required. A lower score is better; beating a basic grid does not imply
beating the published packing record.
