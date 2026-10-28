## Default one-lineage adaptive search; domain display (2026-10-28)

Gerit now defaults to `initial_parents=1` and `max_parents=10`.
A lineage is one active search path with its own current parent, progress
history, and step-size preferences. The population adjustment controller
checks every `population_adjust_interval=20` completed generations:
it can add at most ONE lineage after weak progress, or remove at most
ONE lineage after strong progress, down to a minimum of ONE. The
population does not necessarily hit either limit or return to one
within any given run.

The generic engine's progress output optionally calls a problem adapter's
`progress_display(state)` method. The square adapter supplies
`best_L=<container side>` as the leading field, since this is the
user's primary practical metric. Generic objective scores remain
preserved as independent fields and in best.json. No square geometry
is imported into the general-purpose engine.

CLI default `log_every=10` displays STEP 1 and every tenth completed
generation. Checkpoints default separately to 200; specify 10 if desired.

### Windows CMD: 1000 new generations from previous 500-generation best

    cd /d C:\Physics\Gerit
    git switch experiment/single-lineage-video
    git pull --ff-only origin experiment/single-lineage-video
    cd gerit_core_v1
    py -3 -m unittest discover -s tests -v

    py -3 -u -m examples.square_packing --initial-state results/squares-warm-step-500-4515/best.json --iterations 1000 --initial-parents 1 --max-parents 10 --children-per-parent 10 --population-adjust-interval 20 --reservoir-size 128 --evaluation-budget 120000 --compression-attempts 4 --rotation-attempts 12 --operator-set legacy-hybrid --log-every 10 --checkpoint-every 10 --seed 4516 --output-dir results/squares-singlelineage-1000-4516

Warm-start loading validates the previous 12-square geometry.
Expected starting side is approximately `4.052295013770`; it is the
state only, not a deterministic resume of old RNG or adaptive history.
A fresh output directory preserves earlier best.json files.

## Inheritable generic intensity and warm-start experiment (2026-10-28)

This is a DOMAIN-INDEPENDENT core change. A lineage now stores a private
distribution over three dimensionless mutation intensities (default
`step_scales=(0.3,1.0,3.0)`). Each trial samples intensity, and its
reward is based on objective improvement relative to its own parent.
Probabilities are smoothed with nonzero exploration. New lineages copy
the closest existing lineage's size preferences and continue to learn
independently. This is **not** full policy checkpoint/resumption.

Each lineage now records discrete first and second differences of
its objective *improvement per generation*: `progress_velocity`
and `progress_acceleration`. These are not derivatives of the objective
with respect to the problem's coordinates. Declining and accelerating
failure (both negative) increases the weight of longer steps; improving
negative velocity (negative first / positive second) modestly favors
smaller steps. Sustained stagnation favors longer steps.

Independently of the learned step distribution, an occasional large
jump (`jump_probability=0.08`, doubled after 20 stalled generations)
tests intensity `jump_scale=7`. A global best-ever archive is preserved.
Some nonimproving jump states may be saved as historical branch seeds
if within `absolute_regression` of the current best. There is **no**
proof of avoiding all local minima, nor do these rules guarantee that
a domain operator actually honors intensity. The square adapter adds
`scaled_pose`, which applies the intensity to changes of square center
and orientation. Other preexisting legacy operators only partially or
not at all use the generic intensity argument.

For a five-parent warm start set `--initial-parents 5 --max-parents 10`.
Initial parents are distinct generated alternatives near the supplied
best state when available; a shortfall can occur if distinct feasible
alternatives cannot be found within `branch_seed_attempts` and
`absolute_regression`. Initializing five parents increases cost.
Extra parents are added or removed gradually by the generic progress
controller up to ten; it does not automatically jump to ten at once.

### 500-generation Windows square adapter experiment

    cd /d C:\Physics\Gerit
    git switch experiment/single-lineage-video
    git pull --ff-only origin experiment/single-lineage-video
    cd gerit_core_v1
    py -3 -m unittest discover -s tests -v

    py -3 -u -m examples.square_packing --initial-state results/squares-random-standard-5000-4514/best.json --iterations 500 --initial-parents 5 --max-parents 10 --children-per-parent 10 --population-adjust-interval 20 --reservoir-size 128 --evaluation-budget 60000 --compression-attempts 4 --rotation-attempts 12 --operator-set legacy-hybrid --log-every 20 --checkpoint-every 20 --seed 4515 --output-dir results/squares-warm-step-500-4515

The initial objective must match the loaded previous best:
`4.421749900698131` empty area, and L about
`4.0523758340877185`. The adapter validates all twelve poses before
starting, displays WARM_START and saves a fresh output directory.
This is a WARM START of the state, not a deterministic restart of the
old search run. The budget excludes previous evaluations.

New diagnostics in `status.json` and `run_summary.json` include
`step_stats` and per-lineage `step_weights`, velocity, acceleration,
and stagnation. This experiment is an initial test, not a proof that
learning intensities improves the optimizer. Compare with an equally
budgeted baseline on the *same* starting state and seed.

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
