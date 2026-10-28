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
