# Multiwell Rastrigin benchmark

This experiment tests whether the **general Gerit search engine** can escape
local minima. It does not introduce any square-specific logic.

## Function

Minimize on x,y in [-5.12,5.12]:

    f(x,y) = 20 + x^2 + y^2 - 10 cos(2*pi*x) - 10 cos(2*pi*y)

The global minimum is f(0,0)=0. The function has many distinct local minima,
separated by high-energy barriers. It is not appropriate to conclude from
one successful run that the algorithm will escape every local minimum.

## Why two configurations?

Use the SAME starting point, mutation operators, evaluation budget,
and random seeds to compare:
- single: max_parents=1
- adaptive: max_parents=5 (incremental population changes and rollback)

A successful adaptive run is not sufficient: compare success rate and median
best objective across multiple seeds. The random number streams differ after
population changes; paired seeds improve reproducibility but do not force
identical trajectories.

## CMD

From C:\Physics\Gerit:

    git switch experiment/single-lineage-video
    git pull --ff-only origin experiment/single-lineage-video
    cd gerit_core_v1
    py -3 -m unittest discover -s tests -v
    py -3 -m examples.rastrigin_benchmark --seeds 5 --start-seed 3000 --evaluation-budget 20000 --iterations 3000 --max-parents 5 --population-adjust-interval 20 --output-dir results/rastrigin-5seeds

Output: results/rastrigin-5seeds/comparison.json and separate best.json
and run_summary.json for each seed and method. Use a fresh output directory
for a second benchmark run.

## Measurements

- global_success: objective < 0.001. This is a demanding practical
  threshold, not a mathematical proof of exact optimality.
- visited_basins: number of integer-labeled cells where **any** candidate
  evaluation occurred; NOT the number of distinct local minima found.
- near_center_basins: number of cells where the best observed sample is within
  distance 0.13 of that cell's integer center. This is a rough proxy for
  approaching wells, NOT a rigorous local-minima certificate.
- events: changes in parent population, including expansion/contraction.

This implementation is a minimizer. Finding *every* local maximum and minimum
would require a different task: explicit multi-modal/niching coverage,
stationary-point refinement, and separate maximization or root-finding.

## Scientific caveat

The benchmark includes an unrestricted random relocation operator in BOTH
configurations to provide a fair, broad global-search baseline. Therefore,
reaching the global basin alone does not prove that genealogical backtracking
was the cause. A future ablation should compare with and without history,
branching, and relocation separately, using identical evaluation budgets.

The initial state is deliberately placed away from the optimum at (3.25,-3.75).
