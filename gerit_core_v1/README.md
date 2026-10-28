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

## Limitations

This first independent core does NOT yet run or resume the 12-square experiment.
Only best.json is fully sufficient to recover the solution (with a problem decoder);
the entire optimizer RNG/controller/parent state is not yet resumable.
The algorithm is a heuristic, not a guaranteed global optimizer.
See docs/ARCHITECTURE.md.
