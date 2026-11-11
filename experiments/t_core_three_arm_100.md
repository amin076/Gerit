# Three-arm T-core 17-square experiment

This feature implements a **true three-arm T**: one central 45-degree
diamond with *three* fully edge-connected equal-size diamond neighbours;
one diagonal X arm is absent. The 12 exterior axis-aligned squares from
the previous X-core geometry remain. The 17th square is repositioned
**inside the missing-arm void** (axis aligned) rather than extending
the enclosing container outward.

Code is in `gerit/t_core_geometry.py`, registered under
`t_core_three_arm` in the independently testable
`gerit/symmetry_operators.py`. All four choices for the omitted
diagonal arm can be constructed with `missing_quadrant=ne|nw|sw|se`.

Initial seed bounding side: approximately **4.82855**, strictly
better than a regular 5x5 grid but worse than the earlier
four-2x2-block founder at **4.707146783**. The four-arm X and
three-arm T seed families remain separate; neither is a published
packing solution or claimed as an evolutionary improvement.

The engine `gerit.evolution.evolve`, fitness/diversity selection,
historical revival, two-parent crossover and population logging are
unchanged.

## Windows CMD: update project, then 100 generations

```bat
cd C:\Physics\Gerit
git switch feature/five-square-corner-center
git pull --ff-only
py -3 -m unittest discover -s tests -p test_t_core_geometry.py -v
```

**Recommended first experiment** starts **only** from the T-core,
so its improvement is not masked by the existing better 4-corner seed.
The normal evolutionary engine still fills the other parent slots
through real generation-zero mutation:

```bat
py -3 -u scripts/run_symmetry_three_counts.py --counts 17 --founder-mode t-only --generations 100 --parents 20 --offspring-per-parent 5 --report-every 10 --image-every 10 --out-root results/n17-t-only-100
```

**Control experiment** includes all geometrical seed families and
the T-core seed in the same 20-parent population. Its best result
may begin at 4.707 from the older founder:

```bat
py -3 -u scripts/run_symmetry_three_counts.py --counts 17 --founder-mode all --generations 100 --parents 20 --offspring-per-parent 5 --report-every 10 --image-every 10 --out-root results/n17-t-all-100
```

Each run must have a new output directory. The output includes
`n17/experiment_summary.json`, `n17/best_packing.json`, full
individual lineage and selection logs, `operator_stats`, and
independently certified interval SAT validation. The `founder_mode`
field distinguishes results from the two experimental arms.

Tests: `tests/test_t_core_geometry.py` verifies every omitted-arm
direction, strict zero-tolerance collision checks, independent
interval SAT, and the T-core founder's inclusion without replacing
the older seed. `.github/workflows/gerit-symmetry-multiparent.yml`
also runs real short single-family and multi-family evolutions.
