# Gerit adaptive search — gradual branching and historical recovery

Gerit is problem-independent. A problem adapter defines its objective,
feasibility, metric, mutations, and serialization. The core never knows squares.

## Historical backtracking
Before each generation, Gerit records parent candidates in a bounded history
(`history_depth` generations times `max_parents`).
On a low-progress decision it tries to add exactly one lineage, prioritizing
eligible parent states from preceding generations (one, two, three or more steps
back), then the diverse candidate reservoir and finally up to
`branch_seed_attempts` fresh proposals. A recovered lineage is an independent
search trajectory, not a rewind of the random number generator or all policies.
The best-ever archive is protected. `absolute_regression` limits how far an
alternate parent may fall behind the archived best; `min_distance` requires
diversity. If no valid distinct alternative exists, the event
`population_shortfall` explicitly reports the failure; the engine cannot
guarantee a new feasible branch in an arbitrary problem.

## Local, scale-adaptive notion of progress
Every `population_adjust_interval` generations Gerit measures the global
best objective reduction over that interval. An exponential moving reference
of recent *positive* interval gains is updated with `progress_smoothing`.
The ratio `gain / reference_gain` drives a three-zone
controller:
- ratio < `low_progress_ratio`: attempt to add one parent
- ratio >= `high_progress_ratio`: remove one parent (if more than one)
- otherwise: keep population unchanged

`significant_gain` is ONLY a fallback scale when the very first measured window
has no positive gain, not a fixed cutoff for later improvements. A sequence of
microscopic positive gains can therefore be recognized as good progress.
Problem-dependent noise estimation remains research work.
Zero-gain intervals do not erase the moving positive-gain reference.
The controller never changes population by more than one at a decision.
Population is between 1 and `max_parents`.

## Lineage selection
Each lineage records recent improvements relative to its own parent.
On contraction Gerit computes a combined rank from:
1. current objective, preserving absolute solution quality;
2. average progress over the last `competition_generations` steps,
   preserving the future potential of improving trajectories.

`trend_weight` controls the emphasis on progress trajectory.
Dropping a lineage never drops the best-ever archive. Global record
selection remains based on actual objective, not on trend alone.

## Compute accounting and limitations
The `evaluation_budget` counts all proposals, including attempts to seed
branches. Failed seeding can consume budget. Parents remain feasible; candidate
validity and objective are defined by the adapter. Checkpoints persist
best.json immediately on every new record and status.json periodically;
**full deterministic resume is not yet implemented**.
This is an adaptive heuristic, not a global-optimality guarantee.

## Parameters (defaults)
- `population_adjust_interval=20`
- `max_parents=5`
- `history_depth=120`
- `branch_seed_attempts=256`
- `low_progress_ratio=0.25`, `high_progress_ratio=0.80`
- `progress_smoothing=0.35`
- `trend_weight=0.35`
- `competition_generations=200` (used as lineage trend-memory horizon)
- `significant_gain=1e-6` (numerical progress floor; adapt for problem scale)
- `absolute_regression=0.15`, `min_distance=1e-6`

## Testing and interpretation
Run `py -3 -m unittest discover -s tests -v` from `gerit_core_v1`.
The deterministic synthetic test verifies historical recovery, gradual
expansion and the evaluation cap; another checks one-at-a-time contraction
and progress-sensitive retention. The quadratic example is a smoke test,
not a challenging proof of escape from multimodal local optima.
Future benchmarking must compare against baselines on multiple objective
landscapes with equal evaluation budgets and many seeds.
