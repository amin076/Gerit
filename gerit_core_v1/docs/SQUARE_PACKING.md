## Default initialization changed: random rotated 6x6 (October 2026)

This change belongs ONLY to `examples.square_packing.TwelveSquares`; the
generic search engine and other example problems are unchanged.

Default: `--initial-side 6.0 --initial-mode random --initial-angle-mode random`.
Twelve unit squares are placed sequentially with random centers and
independent uniformly sampled angles in [0, pi/2). Each partial packing is
checked with the existing strict SAT overlap/boundary validator, and a
failed construction is restarted. Defaults are 2000 placement trials per
square and 200 restarts; a failed start reports an explicit error instead
of injecting a grid packing. The initial square has area 36; this is
a starting region, NOT a permanent cap on search and NOT a core-engine
constraint. The domain's objective remains unused area = L^2 - 12.
The existing mutation operators continue to modify angles and centers.

`--initial-mode grid --initial-side 5.0` retains the former 4x3
unrotated baseline only for comparison. The random initializer is
deterministic for a fixed seed. An optional `--initial-angle-mode zero`
can disable random angles for controlled comparison, not by default.

### Windows CMD: pull and run 1000 generations with a fresh seed

    cd /d C:\Physics\Gerit
    git switch experiment/single-lineage-video
    git pull --ff-only origin experiment/single-lineage-video
    cd gerit_core_v1
    py -3 -m unittest discover -s tests -v

    py -3 -u -m examples.square_packing --iterations 1000 --children-per-parent 10 --max-parents 5 --population-adjust-interval 20 --reservoir-size 128 --evaluation-budget 100000 --compression-attempts 4 --rotation-attempts 12 --operator-set legacy-hybrid --initial-side 6.0 --initial-mode random --initial-angle-mode random --initial-placement-attempts 2000 --initial-restarts 200 --log-every 1 --checkpoint-every 20 --seed 4513 --output-dir results/squares-random6-seed4513

The first `INITIAL_CONFIGURATION` and `START` console lines confirm
the new settings; initial objective will be 24 for L=6 because 36-12=24.
The initial best geometry is archived in best.json; latest_packing.png
is created immediately after initialization. This is a fresh run,
not a continuation of the previous L~4 solution. More challenging
random initial layouts can converge more slowly or fail; a single
seed cannot establish superiority.

## Legacy-vs-generic integration audit (new)

Separating search from the square problem was appropriate, but the initial
adapter was **not feature-equivalent** to the old square-specific runner:
- Historical `propose_learned` with ten action families and the legacy
  `LearningController` was omitted; the new adapter now exposes it as
  `learned` alongside `micro`, `contact`, `restructure`, `rotate`, and
  `compress`. Use `--operator-set legacy-hybrid` (default) to include it;
  use `--operator-set basic` to reproduce the earlier five-operator mix.
- The old runner used a domain-specific adaptive controller and per-lineage
  inherited mutation policies. The current generic engine still does NOT
  fully reproduce those policies: the restored learned operator starts with
  a shared adapter policy and shared global learning controller.
- The old runner used 35 compression trials per child by default. The adapter
  exposes `--compression-attempts`; smaller values trade effectiveness for
  speed. They are not equivalent runs.
- The first generic reservoir performed a new quadratic all-pairs diversity
  comparison whenever it exceeded capacity. Now generic reservoir replacement
  requires only O(N) distances to the incoming candidate, avoiding the
  observed performance collapse at the default N=128.
- The generic engine records `operator_stats` (calls, total wall seconds,
  valid candidates, improving candidates) in status.json and run_summary.json.
  These are domain-neutral diagnostics.
- The 5x5 starting arrangement is a regular 4x3 array, not the old
  fresh-nongrid starting distribution. Different initial conditions prevent a
  scientific claim that the engine itself is better/worse from one run.

### Single-seed integration test (Windows CMD)

    cd /d C:\Physics\Gerit
    git switch experiment/single-lineage-video
    git pull --ff-only origin experiment/single-lineage-video
    cd gerit_core_v1
    py -3 -m unittest discover -s tests -v

    py -3 -u -m examples.square_packing --iterations 120 --children-per-parent 10 --max-parents 5 --population-adjust-interval 20 --reservoir-size 128 --evaluation-budget 10000 --compression-attempts 4 --rotation-attempts 12 --operator-set legacy-hybrid --log-every 1 --seed 4511 --output-dir results/squares-legacy-hybrid-seed4511

This run generates the current/final PNG images. It intentionally omits MP4
encoding to keep profiling costs down. Add `--video --fps 30` after confirming
that speed and the generated geometry are acceptable. The best solution
remains protected in best.json. For hard evidence inspect
run_summary.json -> operator_stats, status.json and the final printed
ROTATION_STATISTICS and LEGACY_LEARNING.

Do not claim that angular diversity, structural moves or learned policy are
beneficial until comparable equal-budget multi-seed ablations confirm it.
## Rotation diagnostics and non-axis-aligned search

The initial 5x5 geometry has unrotated unit squares, but rotated poses
are allowed by the existing SAT validator and all square pose models.
Earlier micro/structural/contact operators included rotation; however
one-step strict parent improvement often selects unrotated incumbents,
especially after a near-4 grid develops. Presence of angular proposals
does not guarantee that the best archived packing rotates.

A separate square-domain `rotate` operator now tries a substantial
non-90-degree turn together with translation. It is subject to the
same strict geometric validity tests and the general engine's existing
candidate-history reservoir. Its default `--rotation-attempts 12` is
tunable. The CMD result prints:
- ROTATION_PROBES: calls and geometrically valid rotated proposals
- ROTATION_STATISTICS: number of squares in best-ever packing oriented
  >= 1 degree off an axis, and individual angles modulo 90 degrees

This distinguishes *proposing valid angular solutions* from *selecting
a rotated optimum*. It is entirely possible for valid rotated states
to be proposed but never accepted as a better parent. In that event,
the next research target is generic neutral/downhill lineage management,
not disabling SAT or injecting a known good layout.

Test after pull:

    py -3 -m unittest discover -s tests -v

Rotate-diagnostic quick run:

    py -3 -u -m examples.square_packing --iterations 100 --children-per-parent 10 --max-parents 5 --population-adjust-interval 20 --evaluation-budget 10000 --compression-attempts 2 --rotation-attempts 12 --log-every 1 --seed 4510 --output-dir results/squares-rotation-4510

Do not interpret a rotated trial as a proof of a better optimum; results
must be compared with equal evaluation budgets and independent seeds.

## Updated goal-gap objective and output (October 2026)

The 12-square adapter now minimizes **unused area**, `L*L - 12`, rather than
just the side length. For positive L the two have the same minimizers, but
the saved `best.json` field `objective` now means unused area.
The certified lower bound for unused area is **zero** (area cannot be
negative). It does NOT assert that a zero-gap packing is attainable.

The generic core optionally reads an adapter's `objective_lower_bound`
and scores window progress as the fraction of the remaining certified
objective gap closed. This is compared against a moving baseline of recent
fractions. Early large improvements are not a permanent threshold.
Problems without a trustworthy bound retain the rolling-gain fallback.
The optional `on_generation` callback is independent of search logic.

The square adapter (and **not** Gerit Core) now writes
`latest_packing.png` after each completed generation and
`final_packing.png` at end. With `--video` it also stores one PNG per
generation by default in `frames/` and encodes `packing.mp4` at
`--fps 30`. For 10,000 completed generations this is ~333 seconds of
playback. `--frame-every 5` reduces storage and playback length.
Video requires `ffmpeg` on PATH; static images require Pillow.
Rendering and video creation add disk usage and time.

IMPORTANT: this is an experimental controller. The run may exhaust the
evaluation budget before its requested generation count, and the
population may not contract despite progress.

### Run after git pull (CMD)

    cd /d C:\Physics\Gerit
    git switch experiment/single-lineage-video
    git pull --ff-only origin experiment/single-lineage-video
    cd gerit_core_v1
    py -3 -m unittest discover -s tests -v

Quick run, images:

    py -3 -u -m examples.square_packing --iterations 100 --children-per-parent 10 --max-parents 10 --population-adjust-interval 20 --evaluation-budget 10000 --compression-attempts 4 --log-every 1 --seed 4500 --output-dir results/squares-gap-smoke

Quick run, images and 30 fps video:

    py -3 -u -m examples.square_packing --iterations 100 --children-per-parent 10 --max-parents 10 --population-adjust-interval 20 --evaluation-budget 10000 --compression-attempts 4 --video --fps 30 --log-every 1 --seed 4500 --output-dir results/squares-gap-video

Long run:

    py -3 -u -m examples.square_packing --iterations 10000 --children-per-parent 10 --max-parents 10 --population-adjust-interval 20 --evaluation-budget 1000000 --compression-attempts 8 --video --fps 30 --log-every 1 --seed 4501 --output-dir results/squares-gap-10000

# Twelve unit squares: Gerit Core adapter

This is the first integration of the **domain-independent** Gerit search core
with the historical Gerit rigid-square geometry library. No domain-specific
code has been added to gerit_core/engine.py.

## Objective and constraints
Find a packing of twelve unit squares inside a square of smallest area.
Square i has center (x_i,y_i) and angle theta_i. Squares must not overlap
and each of their four vertices must be within [0,L] x [0,L].
For L>0, minimizing L is equivalent to minimizing area L^2.
Every saved best solution is validated using gerit.geometry.validate_packing
with tolerance=0.0, the existing project's strict numerical SAT test.
This is a numerical optimizer, not a mathematical certificate of optimality.

## Fresh start
No prior best is loaded. The deterministic starting arrangement uses four
columns and three rows of unit squares spaced inside a 5 x 5 container.
The input --initial-side changes the starting box (>= 4).
The starting parent is valid; geometry changes via operators only.

## Domain mutation actions
- micro: existing precise small movements and rotations
- contact: existing geometric contact-guided relocation
- restructure: existing wider structural rearrangements
- compress: existing local compression of valid packings

The generic Search engine learns per-operator probabilities from successful
offspring. Domain operations use the preexisting geometric code.
Each valid child is represented as a Packing(state) with exact side and poses.

## Incremental adaptive branching
Start with 1 lineage, population can grow by at most 1 every
--population-adjust-interval (default 20) up to --max-parents (e.g. 10).
It can contract by at most 1 per interval if locally normalized progress is
good. Older valid states are considered on expansion.
The best-ever solution is stored atomically in best.json on every record.
Seeding failure is reported as population_shortfall.
This controller is experimental: it is NOT guaranteed to contract at all;
the Rastrigin experiment showed it can reach the maximum and remain there.
Do not assume 10,000 generations finish quickly: cost rises with number of
parents and with expensive collision checks.

## Windows CMD

    cd /d C:\Physics\Gerit
    git switch experiment/single-lineage-video
    git pull --ff-only origin experiment/single-lineage-video
    cd gerit_core_v1
    py -3 -m unittest discover -s tests -v

Short smoke test:

    py -3 -m examples.square_packing --iterations 100 --children-per-parent 10 --max-parents 10 --population-adjust-interval 20 --evaluation-budget 10000 --compression-attempts 4 --seed 4500 --log-every 1 --output-dir results/squares-smoke-4500-v2

Full first experiment:

    py -3 -m examples.square_packing --iterations 10000 --children-per-parent 10 --max-parents 10 --population-adjust-interval 20 --evaluation-budget 1000000 --history-depth 120 --absolute-regression 0.15 --significant-gain 0.000000001 --compression-attempts 8 --initial-side 5.0 --seed 4501 --log-every 50 --output-dir results/squares-10000-seed4501

Because each parent produces 10 children, ten parents can require up to
100 evaluations per generation. The engine now prints START once and a STEP line after each generation by default (log_every=1). Each STEP line reports best_L, delta_L, active parents, evaluations, generation_seconds and elapsed_seconds. No output between generation boundaries means a generation may still be computing expensive geometric operators. Use --log-every N to reduce console output.\n\nThe evaluation budget may stop the experiment
before generation 10,000. Raise it if needed, at additional compute cost.

## Outputs
- best.json contains best objective (L) and full geometry (12 center-angle triples)
- status.json contains current generation, evaluation count, active parent count
- run_summary.json contains events, generation and objective

Area = L^2; unused area = L^2 - 12. best.json is saved on each improvement
and survives ordinary interruption; exact continuation of RNG and controller
state is not implemented. This version does not generate MP4 video.

## Scientific test
Always compare to baseline under equal evaluation count and multiple seeds.
Report the best side, area, actual evaluations, generation count,
expansion/contraction events and feasibility. Unlike older experiments,
this one starts from a fresh 5x5 packing rather than a prior 4.00x result.
