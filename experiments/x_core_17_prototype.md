# X-core 17-square prototype (five edge-adjacent diamonds + twelve outer squares)

This construction is an independent **geometry seed** in
`gerit/x_core_geometry.py`, registered as `x_core_fourfold`
in `gerit/symmetry_operators.py`.

## Geometry

- Five identical unit squares are rotated by 45 degrees.
- One is central, the other four lie at signed diagonal offsets
  `(±1/sqrt(2), ±1/sqrt(2))` in the idealized layout.
- These four neighbours share **whole edges** with the central diamond,
  not just point contacts.
- Three additional axis-aligned squares are placed in one quadrant at
  `(r,b), (b,r), (r,r)`, with `r=sqrt(2)+1/2`, `b=0.8`.
- That group is repeated by 90, 180 and 270-degree rotations, giving
  `5 + 4*3 = 17` squares.
- Strict SAT validation uses tiny positive numeric clearance so analytic
  exact contacts cannot become floating-point penetration.

The idealized enclosing side is:
`L = 2 + 2*sqrt(2) ≈ 4.82842712474619`.

With default numerical clearance the actual generated L is slightly
larger than that idealized value, but below 5.

The existing symmetric 2x2-blocks-plus-center family yields around
`4.707146783072`. Therefore **this X-core is geometrically valid but
not a new best**. It is deliberately retained as a different parent
genome for possible later structural mutations or crossover.

## Reproduction and verification

```bat
cd C:\Physics\Gerit
git switch feature/five-square-corner-center
git pull --ff-only
py -3 -m unittest discover -s tests -p test_x_core_geometry.py -v
py -3 -u scripts/run_symmetry_three_counts.py --counts 17 --generations 10 --parents 20 --offspring-per-parent 5 --report-every 5 --out-root results/n17-x-core-ten
```

The `n17/experiment_summary.json` and `n17/run-*/individuals.jsonl`
retain the founder labels and provenance. Exact contact is represented
by a small positive gap in floating-point coordinates and is not falsely
reported as exact computational edge contact. For 18 and 19 the X-core
constructor returns `None` by design until a separate insertion
family is verified.

Only run longer 50 or 500 generation experiments after a controlled
comparison, since this template alone is worse than the previously
validated N17 founder.
