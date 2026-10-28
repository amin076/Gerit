## New: domain-independent objective gap and square visualization

A problem adapter MAY declare `objective_lower_bound` (for minimization).
The engine then measures fractional progress toward this certified lower bound
and compares it with a moving local progress baseline. This does not imply
the bound is attainable. Problems without a bound use rolling gains.
An optional generic generation callback enables outputs separate from search.

The 12-square adapter minimizes **unused area = L^2 - 12**, with a certified
lower bound of 0. In `best.json`, `objective` now means empty area;
`state.container_side` is the side length L. The adapter creates
`latest_packing.png` every generation and `final_packing.png` on completion.
Use `--video --fps 30` to create frame PNGs and `packing.mp4` (ffmpeg required).

Quick updated command:

    py -3 -u -m examples.square_packing --iterations 100 --children-per-parent 10 --max-parents 10 --population-adjust-interval 20 --evaluation-budget 10000 --compression-attempts 4 --video --fps 30 --log-every 1 --seed 4500 --output-dir results/squares-gap-video

See [docs/SQUARE_PACKING.md](docs/SQUARE_PACKING.md).

# Gerit Core v0.1 — generic optimization prototype

This isolated prototype implements a domain-independent adaptive evolutionary search engine.
The existing 12-square optimizer and its experiment files are unchanged.

## Windows CMD quick start

From C:\Physics\Gerit:

    git switch experiment/single-lineage-video
    git pull --ff-only origin experiment/single-lineage-video
    cd gerit_core_v1
    py -3 -m unittest discover -s tests -v
    py -3 -m examples.quadratic --iterations 1000 --children-per-parent 10 --max-parents 5 --stagnation-window 200 --competition-generations 200 --evaluation-budget 20000 --output-dir results/demo

The example minimizes f(x,y)=(x-2)^2+(y+3)^2, whose optimum is (2,-3) with value zero.

## Main contracts

Supply a problem object implementing initial(rng), evaluate(state), feasible(state),
distance(a,b) and encode(state). Supply a mapping of mutation operators:
name -> (state,rng,intensity) -> new_state.

Every Settings parameter has a default and can be passed from a CLI or Python.
Output files: best.json, status.json and run_summary.json.

## Adaptive population and backtracking (v0.2 experimental)

The search engine now adds or removes **one lineage per decision interval** (default
20 generations), using a local moving measure of progress. Alternative branches
can return to historical parent states from earlier generations. Each lineage's
recent improvement trend matters when reducing the population, alongside current
objective quality. See [docs/ADAPTIVE_SEARCH.md](docs/ADAPTIVE_SEARCH.md).

Example with explicit gradual adjustment:

    py -3 -m examples.quadratic --iterations 1000 --children-per-parent 10 --max-parents 5 --population-adjust-interval 20 --trend-weight 0.35 --history-depth 120 --evaluation-budget 20000 --seed 2716 --output-dir results/demo-adaptive

Run tests:

    py -3 -m unittest discover -s tests -v

## Multiwell escape benchmark

To challenge Gerit with many local minima and compare adaptive branching to a
single-parent baseline, run:

    py -3 -m examples.rastrigin_benchmark --seeds 5 --start-seed 3000 --evaluation-budget 20000 --iterations 3000 --max-parents 5 --population-adjust-interval 20 --output-dir results/rastrigin-5seeds

See [docs/RASTRIGIN_BENCHMARK.md](docs/RASTRIGIN_BENCHMARK.md). This is a
benchmark, not evidence of global convergence until results are inspected.

## Twelve-square packing problem adapter (fresh 5 x 5 start)

The new `examples.square_packing` plugs the repository's existing rigorous
numerical square geometry into the generic Gerit engine. It does not modify
the old 12-square runner. Start with a quick smoke test; the 10,000-generation
configuration is computationally heavy.

    py -3 -m examples.square_packing --iterations 100 --children-per-parent 10 --max-parents 10 --population-adjust-interval 20 --evaluation-budget 10000 --compression-attempts 4 --seed 4500 --output-dir results/squares-smoke-4500

    py -3 -m examples.square_packing --iterations 10000 --children-per-parent 10 --max-parents 10 --population-adjust-interval 20 --evaluation-budget 1000000 --history-depth 120 --absolute-regression 0.15 --significant-gain 0.000000001 --compression-attempts 8 --initial-side 5.0 --seed 4501 --log-every 50 --output-dir results/squares-10000-seed4501

Read [docs/SQUARE_PACKING.md](docs/SQUARE_PACKING.md).

## Limitations

This first independent core does NOT yet run or resume the 12-square experiment.
Only best.json is fully sufficient to recover the solution (with a problem decoder);
the entire optimizer RNG/controller/parent state is not yet resumable.
The algorithm is a heuristic, not a guaranteed global optimizer.
See docs/ARCHITECTURE.md.
