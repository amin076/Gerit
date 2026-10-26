# Grid-aware Gerit search (optional v4 continuation)

## Why did the old solver use side 5 for twelve squares?

**It did not initialize a 5×5 packing in recent v3/v4 runs.** It imported the exact 20 final parents from the previous experiment, with sides around 4.00 for the best and possibly larger for diversity. The constant `SIDE_CAP = 5.0` was used for checking generated candidates and to scale each population image. It was not the initial parent side. Legacy `scripts/run_adaptive_v4.py` is unchanged.

For `n` unit squares, the square grid construction establishes a **feasible upper bound** for the optimal enclosing side:

`k = ceil(sqrt(n))`.

It is not a lower bound: elementary area gives `sqrt(n) <= optimal L <= k`. A `k × k` *grid capacity* is available even though not all cells need be filled, e.g. `n=12` uses four columns and three rows, not 16 actual squares. Other examples: n=23 -> k=5, n=26 -> k=6.

## New commands (Windows PowerShell)

```powershell
cd C:\Physics\Gerit
git pull --ff-only
py -3 -m unittest discover -s tests -p "test_grid_bounds.py" -v

# Continue 20 real parents from Round21, WITHOUT injecting any grid:
py -3 scripts/run_adaptive_auto.py --input results/round21-adaptive-v4/selected_population_final.json --generations 300 --seed 2612 --output-dir results/round22-grid-aware
```

This new runner inherits all 20 parents, their personal learning weights, their global learning weights, and the v4 rolling stagnation state. It automatically prints the known grid side, area-based lower bound, real best parent side and its **focused** acceptance cap.

In auto mode (default), `focused_cap = max(k, best imported parent side) + margin` (margin default `0.15`). For *each parent* with larger actual side, mutations may instead use `max(focused_cap, that parent's own side + margin)` to preserve diversity. Thus the existing record above 4 remains usable, and exploratory temporarily worse valid layouts are not arbitrarily eliminated. This cap is **not** a mathematical bound on the optimum. Use `--cap-margin 0.25` to allow more exploration or `--side-cap 5` to replicate the legacy fixed search cap. An explicit numeric cap below the largest imported parent is rejected with a descriptive error.

Population tiles now use **each arrangement's true container side**; they are no longer misleadingly rendered inside a universal 5×5 frame. The numerical L label remains on each tile. Plots and reports use the grid side for the actual `n`, not a hardcoded L=4 line.

## Starting a *separate* experiment from a known grid

```powershell
# Example with 23 squares: a known packing inside L=5
py -3 scripts/make_grid_population.py --squares 23 --output data/grid23.json
py -3 scripts/run_adaptive_auto.py --input data/grid23.json --generations 100 --seed 2323 --output-dir results/grid23-explicit

# With 26 squares the baseline is L=6
py -3 scripts/make_grid_population.py --squares 26 --output data/grid26.json
py -3 scripts/run_adaptive_auto.py --input data/grid26.json --generations 100 --seed 2626 --output-dir results/grid26-explicit
```

The grid generator produces **20 identical known feasible grid geometries** with neutral inherited policies, expressly tagged `initialization_kind=explicit_known_grid_baseline`. It makes **no** claim that evolution discovered the grid. It is an experimental control that may be less diverse than starting with randomized layouts. The search still allows rotated unit squares. To start with saved real evolved parents, use `--input` instead of grid generation.

`requirements.txt` is unchanged. Run artifacts, numerical validity checks, selected individuals, ZIP archives and 101 images for a 100-generation experiment are produced by the continuation runner as before.

## Known limits

- `ceil(sqrt(n))` is a constructive upper bound, **not** an optimality theorem and **not** an instruction to clamp all children below the grid bound.
- A perfect grid baseline can make an experimental fitness line look excellent from generation zero; always report it separately from *evolutionary discovery*.
- Starting from 20 identical grid parents supplies little geometric diversity. Stronger initialization, non-grid seeds and matched-budget comparisons remain open research topics.
- Validation is strict numerical SAT plus independent Shapely checks, not a certified exact proof.