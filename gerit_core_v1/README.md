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

## Limitations

This first independent core does NOT yet run or resume the 12-square experiment.
Only best.json is fully sufficient to recover the solution (with a problem decoder);
the entire optimizer RNG/controller/parent state is not yet resumable.
The algorithm is a heuristic, not a guaranteed global optimizer.
See docs/ARCHITECTURE.md.
