# Gerit

**Gerit** is a Python-first research project for evolutionary optimization of the **Squares in Squares** packing problem.

> **Status: Phase 1 — initial rigid-square geometry implemented.** A dependency-free geometry validator, grid baselines and unit tests are committed. A first seeded evolutionary solver is now implemented. A second independent validation backend has **not** been implemented. No optimization results are claimed.

## هدف پروژه (خلاصه فارسی)

هدف «Gerit» پیدا کردن چیدمان‌های معتبر و هرچه فشرده‌تر برای `n` مربع واحد داخل یک قاب مربعی است. هیچ دو مربع نباید هم‌پوشانی داخلی داشته باشند و هیچ مربعی نباید از قاب بیرون بزند. مربع‌ها اجازه چرخش دارند. هدف کمینه‌کردن ضلع قاب و در نتیجه مساحت و فضای خالی است.

رویکرد اولیه پروژه یک **جست‌وجوی تکاملی مبتنی بر جمعیت** است: تولید چیدمان‌های معتبر، ارزیابی هندسی، جهش و بازآرایی، انتخاب والدها، نگهداری بهترین جواب‌های معتبر و تکرار نسل‌ها. این رویکرد از ایده‌های پژوهشی [Melakat](https://github.com/amin076/melakat) و چرخه جمعیت/اعتبارسنجی [Siperisk](https://github.com/amin076/siperisk) الهام می‌گیرد، اما یک حل‌گر هندسی جدید لازم دارد. نتیجه بهتر در هر نسل تضمین نمی‌شود؛ فقط با نگهداری نخبگان، بهترین نتیجه ثبت‌شده بدتر نخواهد شد.

## Problem definition

Given `n` closed unit squares, find translations `(x_i, y_i)`, rotations `theta_i`, and the smallest axis-aligned square container with side length `L` such that:

1. Every unit square lies completely within `[0,L] × [0,L]`.
2. The **interiors** of any two unit squares are disjoint. Boundary contact is allowed.
3. The objective is to minimize `L`, equivalently `L²` or unused area `L² - n`.

For an illustrative first experiment, use **n = 17**, starting with a valid axis-aligned placement inside a **5 × 5** container (`L = 5`, area `25`, unused area `8`). A second benchmark is **n = 11** (`L = 4` grid baseline). These are baselines, not solutions claimed to be optimal.

An accepted result must include the container side length and all `n` square centers and angles, plus independently checked geometric validity. A smaller reported `L` is **not** an improvement if any square overlaps or crosses the container boundary.

## Initial research hypothesis

Can a population of valid square packings, evolved through collision-aware mutations, selection and diversity preservation, discover smaller valid containers than simple grid baselines?

We will compare two families under the **same budget of geometric evaluations**:

- **Baseline search:** independent random restarts and local geometric improvement without a population-based resource economy.
- **Evolutionary search:** a population of placements, parent selection, geometrically valid mutation/repair, elite retention, and diversity-preserving exploration.

A later optional experiment may adapt Melakat-inspired scarce computational resources: evaluation budgets allotted to candidate lineages, with resource accounting. This is a **testable experimental variant**, not an assumed improvement.

## Proposed evolutionary cycle

1. **Initialize.** Construct multiple independently randomized, valid placements; include a simple grid baseline as a control.
2. **Represent.** One individual is a full packing: container length `L` and `n` rigid-square poses `(x, y, theta)`.
3. **Mutate.** Try translations, rotations, moves of groups, partial repacking and occasional large perturbations. In strict-validity mode, reject any invalid candidate; no invalid state enters the breeding population.
4. **Validate.** Use a robust geometric test for square/container boundaries and square/square interior intersection (e.g. a separating-axis test), with a documented floating-point tolerance policy. An independent validator rechecks promoted records.
5. **Improve.** Attempt to reduce `L`; local moves may be accepted for exploration even if they do not immediately improve the global record.
6. **Select.** Keep an elite archive of the best validated packing(s), plus diverse viable individuals. Avoid premature convergence to one arrangement.
7. **Repeat.** Save deterministic seeds, lineages, candidates, costs and improvements; stop at a declared evaluation/time budget.

**Invariant:** `best_valid_L(t+1) <= best_valid_L(t)` if the elite archive is retained. This guarantees non-regression of the **record**, not improvement in every generation or global optimality.

### Important engineering distinction

A *valid arrangement* is not the same thing as a *continuous collision-free physical animation*. A solver may propose a move whose start and destination are valid without asserting that the straight-line path between them is physically feasible. A future physical-motion mode would require swept collision detection or path planning. Visualizations must accurately label whether they show proposal/acceptance events or actual collision-free trajectories.

## Planned Python architecture

```text
gerit/
  __init__.py
  geometry.py        # rotated unit squares, container checks, independent validity
  packing.py         # immutable individuals, serialization, canonical metrics
  initialization.py  # valid grid and randomized starting populations
  operators.py       # translation, rotation, group moves, repair/repacking
  evolution.py       # populations, selection, elite archive, diversity
  experiments.py     # fixed-seed campaigns and equal-budget comparisons
  cli.py             # reproducible command-line runner
tests/
  test_geometry.py   # contacts, overlaps, rotations, out-of-bounds, tolerances
  test_evolution.py  # no-invalid-individual and elite non-regression properties
results/              # generated reports; not ground truth by itself
```

This layout is a **proposal**, not a claim that these files already exist. Initial implementation targets Python 3.12+, using the standard library where practical. Dependencies will be justified as they are introduced.

## Scientific and engineering principles

- **Validity before scores:** infeasible packings cannot win or silently enter the elite archive.
- **Rigid squares:** placement geometry uses unchanged unit side lengths; no scaling or deformation.
- **Report real metrics:** record `n`, `L`, `L²`, unused area `L²-n`, seed, evaluation count, runtime, validity and best-so-far history.
- **No fabricated progress:** percentages indicate consumed search budget, never presumed convergence or optimality.
- **Diversity is measurable:** include geometric/structural diversity metrics rather than rewarding arbitrary differences.
- **Reproducibility:** versioned configuration, fixed RNG seeds, output hashes and independent verification; retain unsuccessful runs.
- **Fair comparisons:** compare against simple baselines at matched evaluation budgets and multiple seeds; report distributions, not cherry-picked runs.
- **No novelty claims without evidence:** matching a known packing is reproduction; beating a documented bound requires careful independent checking and provenance.
- **No changes to source projects:** Melakat and Siperisk remain separate; any reused code requires explicit attribution, license preservation and appropriate tests.

## Milestones

- **M0 — Specification (current):** document goal, constraints, baselines, acceptance criteria and architecture.
- **M1 — Geometry & verification (initial implementation complete):** unit-square geometry, SAT collision detection, container boundaries, bounding-square metrics, tests and valid grid baselines. Additional independent high-precision validation remains future work.
- **M2 — Non-evolutionary control:** deterministic random-restart/local-search benchmark for n=11 and n=17.
- **M3 — Evolutionary prototype (implemented as an experimental baseline):** seeded population, subset relocation/rotation, strict destination validity, fitness/diversity selection, elitism and JSON generation histories. Results and performance must still be benchmarked.
- **M4 — Comparative experiments:** matched-seed, matched-budget evaluation against M2; independently validate archived best candidates.
- **M5 — Melakat-inspired budget policy:** optional energy/resource-allocation experiment with ablation controls.
- **M6 — Visualization & Kaggle adapter:** replay actual algorithm events and, after checking official competition rules/format, add a compatible submission exporter.

## Acceptance criteria for a first genuine improvement

For n=17, an example milestone is finding a **validated** packing with `L < 5`. The run must include coordinates, angles, a reproducible seed, a documented number of objective evaluations, and a second validator's report. We will not call this a global optimum.

## Related research and inspiration

- [Melakat](https://github.com/amin076/melakat): digital organisms, bounded energy/memory, reproduction, mutation, genealogy, deterministic experiments. Melakat deliberately avoids an explicit externally rewarded fitness function; Gerit deliberately has one.
- [Siperisk](https://github.com/amin076/siperisk): verified candidate admission, inter-generation population selection, evidence ledger, and provenance. Its mathematical verification mechanisms are **not** directly a geometric packing solver.
- [Gareen](https://github.com/amin076/gareen): formal mathematical research tooling; potential future role in formalizing selected geometric claims, not required for initial numeric optimization.
- [Kaggle — Squares in Squares](https://www.kaggle.com/competitions/squares-in-squares): motivating competition. Official rules, evaluation and submission requirements must be checked before competition-specific integration.

## License

No license is declared by this README. Before copying implementation code from other projects, review the applicable licenses and attribution requirements.

---

Gerit begins as a **research experiment**, not as a claim that evolutionary search necessarily outperforms established square-packing methods. The first priority is a trustworthy geometric validator and an honestly measured baseline.


## Configurable experiments (scaffold implemented)

Parameters are **not hard-coded into the evolutionary engine**. The first Python configuration/CLI scaffold is committed under `gerit/config.py`, `gerit/__main__.py`, and `configs/five-squares.json`. It **validates and previews** an experiment; it does **not** yet run evolution or validate geometry.

Run a configuration preview:

```bash
python -m gerit --config configs/five-squares.json --dry-run
python -m unittest discover -s tests -v
```

Example configuration:

```json
{
  "schema_version": "gerit-run-config-0.1",
  "n_squares": 5,
  "initial_population": 20,
  "next_generation_population": 20,
  "offspring_per_parent": 5,
  "selection_groups": [
    {"method": "fitness", "share": 0.75},
    {"method": "diversity", "share": 0.25}
  ],
  "initialization_source": "grid_mutations",
  "initial_container_side": 3.0,
  "diversity_metric": "center_distances_angles",
  "seed": 17,
  "max_generations": 100,
  "max_evaluations": 100000
}
```

- `initial_population` means the number of initial parents and may differ from `next_generation_population`, the number retained after selection. `offspring_per_parent` is independent of both.
- Selection quotas are allocated by the **largest-remainder** rounding rule, so they always sum to the desired next-generation size even for totals like 30 (75%/25% becomes 23/7).
- Current registered selection groups are `fitness` (smallest **validated** enclosing-square side) and `diversity` (maximize distance from already selected layouts subject to validity and a defined quality ceiling). The concrete selection engine and distance function are **not implemented yet**.
- The selection-group schema is extensible (`method`, `share`, `options`). A future third method such as `novelty` can be added by **implementing and registering** it; unknown methods currently raise a clear error rather than silently pretending to execute.
- Initialization sources are `grid_mutations`, `random_valid`, `file`, and `agent`. The `file` mode requires an `initialization_file` path; `agent` requires an `agent_adapter`. These are **declared future adapters**, not yet runnable generators.
- Human-drawn layouts should enter through a separate user-interface/coordinate-conversion adapter and use the same file schema and independent geometry checker as generated layouts. Agent-generated layouts are untrusted proposals and require validation; neither visual resemblance nor an agent assertion is proof of feasibility.
- Seed, generation/evaluation budgets and the diversity metric are explicit to support fair tests. More computational controls (workers, CPU/GPU backend, wall-time) may be added as versioned fields when execution backends exist.

**Research design:** compare grid-only, randomized valid initial populations, and later optional agent/human-proposed seed populations under the same evaluation budget. Do not assume agents produce higher-quality initial placements without measured evidence.


## Phase 1 — geometry (implemented)

The initial numerical geometry core is dependency-free (Python 3.12+).

- `gerit/geometry.py`: immutable `Square(x, y, angle)` (angle **in radians**, side length always 1), `Packing`, `ValidationResult`.
- `square_vertices(square)`: rotated unit-square vertices.
- `squares_overlap(a,b,tolerance=1e-10)`: separating-axis test (SAT) for interior overlap; boundary contact is allowed.
- `square_inside_container(square, side)`: corners constrained to `[0,side]^2`.
- `validate_packing(packing)`: indices of overlapping pairs and out-of-bounds squares.
- `minimum_bounding_square(squares)`: rebase a **fixed** arrangement into a tight axis-aligned square envelope; this does not optimize/rearrange or repair collisions.
- `unused_area(packing)`: `L²-n` for valid packings; rejects invalid geometry.
- `grid_baseline(n)`: exact row-major grid initial condition (n=5 → 3×3, n=17 → 5×5).
- `tests/test_geometry.py`: numerical geometry regression tests.

Quick check:

```bash
python -m unittest discover -s tests -v
python - <<'PY'
from gerit.geometry import grid_baseline, validate_packing, unused_area
packing = grid_baseline(5)
print(packing.container_side, validate_packing(packing).valid, unused_area(packing))
# 3.0 True 4.0
PY
```

### Numerical precision boundary

The default SAT tolerance is `1e-10`. Penetrations no larger than this tolerance **may be classified as contact**; likewise, boundary overruns up to tolerance may be accepted. This is an explicit approximate numerical policy, **not an exact proof of feasibility**. Before claiming a record or submitting to a competition, revalidate with a separate higher-precision or certified geometry implementation and an appropriate safety margin. The proposed independent `Shapely`/GEOS-based checker is a future milestone and is not claimed implemented.

The core validates snapshots of rigid squares, not their swept collision-free physical motion. Any evolution or visualization must distinguish accepted destination states from actual trajectories.

### Implementation status

Phase 1 geometry was exercised against eight local checks before GitHub upload (valid grids, rotated unit edges, legal contact, overlap, out-of-bounds, tight bounding square, unrepaired overlaps and invalid inputs). CI in the repository has not yet independently confirmed them. The evolutionary engine is still pending.


## Phase 3 — executable evolutionary motor (experimental)

The first **actual evolutionary search** is implemented in `gerit/evolution.py` and invoked by `python -m gerit`. It makes real geometric proposals and runs the Phase 1 collision validator; progress is **not animated, precomputed, or guaranteed**.

Run from repository root:

```bash
python -m unittest discover -s tests -v
python -m gerit --config configs/five-squares.json --dry-run
python -m gerit --config configs/five-squares.json --output results/five-squares-latest.json
```

Outputs include valid best-known packing coordinates and angles in **radians**, its measured side/area/unused area, exact run configuration, numeric-validation status, evaluations consumed, accepted children, and each generation's best-so-far value.

The current evolutionary baseline:
- Starts with an axis-aligned valid grid packing and generates initial variations by random validated relocations/rotations.
- Mutates a randomly selected subset (sometimes the entire configuration). Candidate partial placements and completed offspring must pass rigid-square SAT validation at numeric tolerance **zero**. A proposed displacement is **not** asserted to have a physically traversable collision-free path.
- Scores a feasible offspring by the axis-aligned tight enclosing square `L`; retaining all parents before selection guarantees preservation of the best observed valid result.
- Selects configured fitness elites, plus a farthest-first diversity allocation based on unlabeled center distances and relative angle signatures.
- Enforces configured evaluation and generation limits and records best-so-far history.
- Retains validity but not necessarily distinctness when too few unique survivors exist; duplicates may be carried to fill the configured population.
- Does **not** implement GPU/CPU worker parallelism, human drawing, agent/file initialization, crossovers, physical motion constraints, or a global optimum proof. `file` and `agent` initialization fail explicitly rather than silently using substitute parents.

**Important performance caveat:** this first baseline uses rejection sampling for random repositioning, which can become extremely inefficient for densely packed solutions. It is a real search implementation but has not been shown to reach the known optimal five-square packing. Contact patterns and group rearrangement operators will be refined after measurement. The approximate diversity proxy does not perfectly identify every rotationally equivalent configuration.

**Reproducibility / validity:** seeded deterministic random search is covered by regression tests in `tests/test_evolution.py`. Initial feasibility is checked numerically with zero SAT penetration tolerance, but floating-point arithmetic is not a certified proof. Independently verify any claimed result before submitting or publishing.

### Development notes

The initial strategy uses `grid_mutations` and `random_valid` initialization modes. The latter means independently mutated, strictly valid configurations from the grid control — **not** mathematically uniform sampling from all feasible packings. Repeated identical individuals may be present if the budget is exhausted or valid distinct candidates cannot be generated. The selection shares use the versioned configuration already documented above.
