## Next problem: 13 freely rotated unit squares (2026-10-29)

The packing adapter accepts `--square-count` (default 12) without
changing the generic Gerit engine. The objective is the actual unused
area `L*L - square_count`; the image labels and grid/random initialization
also adapt to the requested number. Existing `TwelveSquares` imports remain
supported. Do not warm-start the 13-square run using a 12-square file.

The exact optimum for 13 unit squares is `L = 4` (Wolfram Bentz, 2010).
This makes it a useful known-answer transfer test before attempting an
unknown case. A 100-generation random-start smoke run, from the
`gerit_core_v1` directory:

    py -3 -m unittest discover -s tests -v

    py -3 -u -m examples.square_packing --square-count 13 --iterations 100 --initial-parents 1 --max-parents 10 --children-per-parent 10 --population-adjust-interval 20 --reservoir-size 128 --evaluation-budget 200000 --initial-mode random --initial-angle-mode random --initial-min-center-distance 2.0 --initial-side 8 --compression-attempts 4 --rotation-attempts 12 --operator-set legacy-hybrid --log-every 10 --checkpoint-every 10 --seed 4526 --output-dir results/squares-13-fresh-100-4526

The initial unused area at side 8 is 51 (not 52). The exact optimal
unused area is 3 (not 0), so the engine's generic lower bound of zero
remains valid but not tight for this problem. Results from this smoke
run are not directly comparable to the 12-square scores.

## Traceable global-best records and late lineage credit (2026-10-29)

Each branch now has a stable, monotonically allocated `lineage_id`
and `parent_lineage_id`. Every new global-best evaluation records
`generation`, `evaluation`, objective and previous objective,
`lineage_id`, source operator, dimensionless intensity, originating
explorer operator and move type (regular/jump/initial). The most
recent record's origin is written to `best.json` and `status.json`;
the ordered, complete records list is written into
`run_summary.json` and the event log. This provides provenance of
the direct move that **produced** a global record, not a mathematical
proof that an early ancestor move caused it.

An exploratory lineage preserves its origin after its initial
protected `explorer_generations` interval expires. If that same
living lineage later first beats its **original parent baseline**,
the engine records `explorer_late_success` and applies a bounded
credit to the initiating operator. The lineage can receive this
late credit only once; any on-time credit already received is
tracked to prevent duplicate reward. Branch removal ends its
opportunity to receive late credit. The global best remains
protected throughout, independently of which lineage currently
owns it.

Run tests and continue 500 generations using the previous best:

    cd /d C:\Physics\Gerit
    git switch experiment/single-lineage-video
    git pull --ff-only origin experiment/single-lineage-video
    cd gerit_core_v1
    py -3 -m unittest discover -s tests -v

    py -3 -u -m examples.square_packing --initial-state results/squares-dual-memory-500-4519/best.json --iterations 500 --initial-parents 1 --max-parents 10 --children-per-parent 10 --population-adjust-interval 20 --evaluation-budget 60000 --compression-attempts 4 --rotation-attempts 12 --operator-set legacy-hybrid --log-every 10 --checkpoint-every 10 --seed 4520 --output-dir results/squares-provenance-500-4520

Expected warm-start square side: `4.048362633923`.
This restores the final geometry, not the prior policies or RNG state.

## Dual-timescale, quality/cost and delayed-credit operator learning (2026-10-29)

The generic engine now mixes a persistent lifetime utility mean with
a bounded recent learning window (120 calls per operator, 45% weighting).
Recent changes in effectiveness therefore influence new choices without
erasing the cumulative evidence. All operators retain a nonzero
selection probability via the existing `exploration_floor`.

The per-attempt utility measures **normalized objective gain** and
**measured time cost**. The score is zero for non-improving proposals;
for an improving proposal it is a capped function of the relative
improvement, divided by `1 + elapsed / mean_operator_elapsed`.
The normalization uses only generic scores and wall-clock time: the
core has no knowledge of positions, rotations, or square geometry.
Execution-time observations may vary across machines, so identical
random seeds need not yield identical results when runtime-sensitive
operator selection changes.

An exploratory lineage now remembers the **operator that created its
initial jump**. If the explorer finishes its protected multi-generation
trial better than its origin parent's starting score, a bounded delayed
credit is allocated to that *originating* operator. This is a heuristic
credit assignment, not a full causal attribution to every intermediate
move. Expiring explorers that do not surpass their baseline get no
delayed reward. Explorer success and operator attribution appear in
`explorer_complete` events.

Settings:
- `recent_learning_window=120`
- `recent_learning_mix=0.45`
- `utility_gain_scale=25.0`
- `delayed_credit_scale=0.5`

In `status.json` and `run_summary.json`, `operator_memory`
now contains `attempts`, `successes`, `utility_sum`,
`recent_utilities` and `delayed_credit`. An operator's
`operator_weights` is a mixed posterior utility preference, **not**
a direct probability until normalized with the exploration floor.

### Windows CMD smoke test: 500 generations from latest saved best

    cd /d C:\Physics\Gerit
    git switch experiment/single-lineage-video
    git pull --ff-only origin experiment/single-lineage-video
    cd gerit_core_v1
    py -3 -m unittest discover -s tests -v

    py -3 -u -m examples.square_packing --initial-state results/squares-persistent-learning-500-4518/best.json --iterations 500 --initial-parents 1 --max-parents 10 --children-per-parent 10 --population-adjust-interval 20 --evaluation-budget 60000 --compression-attempts 4 --rotation-attempts 12 --operator-set legacy-hybrid --log-every 10 --checkpoint-every 10 --seed 4519 --output-dir results/squares-dual-memory-500-4519

Warm start should print an initial enclosing square side of about
`4.050165559267`. The previous best state is the starting geometry,
but no prior learning state is resumed. Keep earlier run directories
for comparison.

## Persistent evidence-based learning memory (2026-10-29)

The earlier EMA reward update frequently drove **every** operator weight to
0.02 and every lineage step-size weight to 0.05 after long periods of
zero immediate improvements. This erased distinctions between previously
successful moves. The core now maintains cumulative attempts and successful
improvements, with fixed low-rate pseudocounts:

    preference = (learning_prior_successes + successes) /
                 (learning_prior_trials + attempts)

Defaults: `learning_prior_successes=0.2`,
`learning_prior_trials=20`. Each operator has a global evidence record
(`operator_memory`), while every lineage has its own step-size
`step_attempts` and `step_successes`. New lineages inherit *copies*
of these counts, so later experience diverges. No extra domain concepts
are introduced to the engine.

The existing guaranteed exploration floor and progress-trend intensity
bias remain. Lifetime evidence means that preferences can become
slower to react over very long runs; this is a deliberate first step
toward preserving rare events, NOT proof of optimal adaptive learning.
A future controlled comparison can assess bounded windows, hierarchical
priors, and delayed multi-generation credit. Existing settings
`learning_rate` and `lineage_step_learning_rate` are retained for
configuration compatibility but are no longer used in these two
evidence-based preference updates.

New `status.json` fields: `operator_memory` and lineage-specific
`step_attempts` and `step_successes`.
`run_summary.json` also records `operator_memory` and
`operator_weights`. Prior best.json files remain compatible since
a warm start loads state geometry only.

### CMD check and continuation from the previous best

    cd /d C:\Physics\Gerit
    git switch experiment/single-lineage-video
    git pull --ff-only origin experiment/single-lineage-video
    cd gerit_core_v1
    py -3 -m unittest discover -s tests -v

    py -3 -u -m examples.square_packing --initial-state results/squares-diverse-explorers-500-4517/best.json --iterations 500 --initial-parents 1 --max-parents 10 --population-adjust-interval 20 --evaluation-budget 60000 --compression-attempts 4 --rotation-attempts 12 --operator-set legacy-hybrid --log-every 10 --checkpoint-every 10 --seed 4518 --output-dir results/squares-persistent-learning-500-4518

Expected geometric warm-start side: `4.050381047578`.
Use equal starting state and evaluation budget for a controlled baseline.

## Genuine branch diversity and multi-generation escape trials (2026-10-29)

The core now computes per-generation pairwise distances among **active**
lineages using only the problem's supplied `distance(a,b)` method.
`population_diversity` reports minimum, mean, maximum, pairs, and
the effective threshold, in the *problem-defined distance units*.
The scale is adaptive: `max(min_distance, diversity_fraction *
median(distance(best, stored_candidate)))` with a default fraction
of 0.10. This avoids hardcoding geometry-specific units; distance
semantics remain the responsibility of each problem adapter.

Population expansion now prefers a historical candidate that is
furthest from its nearest active lineage rather than simply the newest
historical snapshot. All new branches must pass the current diversity
threshold. This encourages distinct candidate states but does NOT
mathematically prove that search basins or futures are independent.

The existing jump sampler may seed a protected explorer lineage.
Up to `max_explorers=2` exploratory paths can run concurrently
for `explorer_generations=15` generations; they may start with a
candidate slightly worse than the best (bounded by
`absolute_regression`). During the trial, the explorer may accept
non-improving local candidates (with probability
`explorer_uphill_probability=0.20`) subject to a loss ceiling.
Protected explorers cannot be deleted by population contraction
while their trial is in progress. At expiry the core compares the
explorer's final score to its original parent's score and records a
`explorer_complete` event. The global best-ever archive remains
protected throughout. Neither the diversity guard nor exploration
is a guarantee of escaping every local minimum.

The progress reports in `status.json` and `run_summary.json` now
include `population_diversity` and `explorer_stats`: spawned,
expired, improved_baseline, uphill_steps, rejected_duplicate and
rejected_capacity. The event log includes explorer start/end events.

### Windows CMD: 500-generation comparison from previous 1000-generation best

    cd /d C:\Physics\Gerit
    git switch experiment/single-lineage-video
    git pull --ff-only origin experiment/single-lineage-video
    cd gerit_core_v1
    py -3 -m unittest discover -s tests -v

    py -3 -u -m examples.square_packing --initial-state results/squares-singlelineage-1000-4516/best.json --iterations 500 --initial-parents 1 --max-parents 10 --children-per-parent 10 --population-adjust-interval 20 --reservoir-size 128 --evaluation-budget 60000 --explorer-generations 15 --max-explorers 2 --diversity-fraction 0.10 --compression-attempts 4 --rotation-attempts 12 --operator-set legacy-hybrid --log-every 10 --checkpoint-every 10 --seed 4517 --output-dir results/squares-diverse-explorers-500-4517

Starting square side should be about `4.050532414419`.
The old best is only a geometric warm start, not a resumed policy/RNG
state. This comparison should ideally be accompanied by an equal-budget
baseline from the same state and seed.

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
