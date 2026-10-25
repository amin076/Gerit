# Gerit

**Gerit** is a Python-first research project for evolutionary optimization of the **Squares in Squares** packing problem.

> **Status: Phase 0 — research specification and roadmap.** No optimization results are claimed yet. The initial baseline, solver and independent geometric validator are planned, not implemented.

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
- **M1 — Geometry & verification:** implement square geometry, collision and boundary validators; add adversarial tests and known-valid baselines.
- **M2 — Non-evolutionary control:** deterministic random-restart/local-search benchmark for n=11 and n=17.
- **M3 — Evolutionary prototype:** population, mutation, selection, elitism, diversity and generation histories.
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
