# Five-square study: four corners and one rotating center

This is a new, **separate** experiment in the existing Gerit repository.
The generic evolutionary search in gerit/evolution.py is NOT replaced.
The source initial state is exactly four axis-aligned unit squares at
(0.5,0.5), (2.5,0.5), (0.5,2.5), (2.5,2.5), and the fifth at (1.5,1.5).
All angles start at zero; initial L=3.

## Search mechanism

Each angle proposal rotates ONLY the central unit square. Four corner unit
squares move inward symmetrically by a shared offset. Binary search finds
a feasible contraction under the existing Gerit SAT collision validator.
A small safety clearance is retained to prevent uncertain contacts.
Proposals include Gaussian local mutation and random angle restarts.
This is a specialized coordinated structural mutation/operator suitable for
future comparison against generic evolutionary mutation, not proof that the
general-purpose algorithm can discover it from a random grid.

The goal is to find a feasible L<3 and improve Kaggle score for N=5;
never treat a seed or a published analytic value as an evolutionary discovery.
A separate interval-arithmetic validator independently checks the final
floating-point configuration before exporting a five-row CSV.

## Run

    python -m pip install -r requirements.txt
    python -m unittest discover -s tests -p "test_five_square_corners.py" -v
    python scripts/run_five_square_corners.py --seeds 2715 2716 2717 --proposals 250 --out results/five-square-corner-center

Output folder is new and is never overwritten. It contains:
initial_seed.json, initial_seed.svg, one trial_<seed>.json per restart,
best_result.json (with actual five square coordinates),
best.svg, comparison.json, trial_results.csv, and five_square_partial.csv.
GitHub Actions runs the same exact experiment and uploads all outputs.

Baseline: side L=3, score 3/sqrt(5)-1 = 0.3416407865.
Independent mathematically known packing: L=2+sqrt(2)/2 ≈ 2.70710678.
The experimental method should APPROACH this value, not claim to prove
global optimality. Small safety clearance intentionally produces a slightly
larger L than the theoretical contact-bound result.

The output can be ingested by the existing Kaggle scan as best.squares after
copying the archive locally. Do not modify historical experiments or the main
solver without independent benchmarks.
