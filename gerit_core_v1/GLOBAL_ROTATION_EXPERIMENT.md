# Global rigid rotation: controlled ablation

This experiment **never** initializes with grid placement or zero angles.
The two arms share an independently generated, feasible random geometry
with 18 rotated unit squares in a 12×12 initial container. This geometry
is generated once per comparison and saved as `random_generation_zero.json`.

## Pull the experimental branch on Windows 11

```powershell
cd C:\Physics\Gerit
git fetch origin
git switch experiment/global-rotation-ablation
git pull --ff-only origin experiment/global-rotation-ablation
cd gerit_core_v1
```

Do not merge into main until the geometry tests and local experiment pass.

## Geometry test (before long experiments)

```powershell
py -3 -m unittest discover -s tests -p "test_global_rotation.py" -v
```

If this fails, stop and report the traceback. There is no reason to start
a long run with an unverified geometry routine.

## Fast paired smoke comparison (20 generations)

```powershell
py -3 -m examples.compare_global_rotation --generations 20 --seed 4540 --initial-side 12 --out results/global_rotation_smoke
```

Check `results/global_rotation_smoke/random_generation_zero.json`.
All 18 positions and angles must be irregular; the random angles are
drawn independently in [0, π/2) (uniform by square symmetry). This
is **not** a previous solution and neither arm begins from a grid.

## Requested 1000-generation paired experiment

```powershell
py -3 -m examples.compare_global_rotation --generations 1000 --seed 4540 --initial-side 12 --out results/global_rotation_ablation
```

For the 1000-generation experiment both runs use:

- square-count=18, initial-mode=random, initial-angle-mode=random
- first generation saved from a new 12×12 random valid packing
- one initial parent, four maximum active parents, ten children per parent
- adaptive historical enabled; two forward + two historical branch slots
- same search seed; 350000 total evaluation limit per run
- fixed operator set, unchanged generic evolutionary engine
- **only independent variable**: `--global-rotation` off vs on

Results:

- `random_generation_zero.json`: common random source geometry and SHA-256
- `without_rotation/best.json`, `with_rotation/best.json`
- `without_rotation/global_rotation_stats.json`, corresponding on stats
- `without_rotation.log` / `with_rotation.log`
- `comparison.json`: side improvement, wall-time multiplier and direct
  fraction of time spent computing global rotation
- final and intermediate packing images; genealogy and status JSONs

Rotation-enabled mode optimizes the outer **axis-aligned** bounding square
over all common rigid orientations, with the relative geometry of the
18 squares unchanged. The global rotation is applied inside the domain
adapter before evaluation. No code in the generic evolutionary engine
is changed. This is a geometry-specific advantage under test, not a
hardcoded grid, reward for zero-angle squares, or reward for side=5.

**Methodological cautions:** same initial packing + same random search seed
do not imply identical evolutionary trajectories, because canonicalization
changes parents and therefore operator behavior. Equal generations need
not produce equal counts of evaluated candidates. Compare number of
evaluations and wall time as reported. A single paired seed is a pilot,
not statistical evidence. Repeat at multiple distinct seeds only after
checking validity, output consistency, and timing. If global rotation is
expensive, implement a mathematically safe lower-bound filter (not an
unverified approximate skip). Time spent creating and validating the
shared start is excluded from both arm runtimes.

## Mathematics and limitations

For the convex hull vertices of all unit-square corners, minimize
`max(projected_width(θ), projected_height(θ))` over θ in [0, π/2].
Hull-edge events divide the angular range into intervals with fixed
support vertices. In each interval both projections have form
`A*cos(θ)+B*sin(θ)`. The optimum is at an interval endpoint,
a derivative-zero point of either projection, or their crossing.
The routine enumerates all those candidates (no random angle search).

The solver is exact in angle in the real-number model, subject to floating
point tolerance in Python. Strict collision validation of a rotated
contact-rich packing can fail from roundoff; in that case the original
valid candidate is kept and the rejection counted in the timing report.

The run does **not** optimize a known solution or preload a previous best.
No global optimum for the 18-square packing problem is claimed.
