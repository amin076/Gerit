# Gerit — new independent 12-square experiment (25 × 300)

This protocol **does not read old `results/`, parent coordinates, reward weights or stagnation windows**. It uses current algorithm code but starts a new experimental trial with a deterministic random seed. The constructive grid is a legitimate algorithmic primitive alongside stochastic exploration and local compression; its presence does not imply that L=4 was newly discovered by evolution.

## Windows PowerShell

```powershell
cd C:\Physics\Gerit
git pull --ff-only
py -3 -m unittest discover -s tests -p "test_fresh_25.py" -v
py -3 scripts/run_fresh_25.py --squares 12 --population 25 --structural-seeds 7 --generations 300 --offspring-per-parent 5 --seed 2715 --output-dir results/fresh12-p25-g300
```

No `--input` parameter is present. No previous `results` files are loaded. **Do not delete previous results** unless you independently choose to; preserving them does not influence this trial. Existing output directories are never overwritten; use a new output name for subsequent runs.

## Initialization — generation 0

- 7 geometrically distinct connected all-parallel integer-cell arrangements (from `gerit.connected_tilings.choose_tilings`), including a guaranteed feasible `L=ceil(sqrt(12))=4` baseline.
- 18 other arrangements sampled reproducibly with new randomness, combining rigidly rotated blocks, jittered/tilted sparse contacts and scattered lattice occupancy.
- All 25 are strictly checked for non-overlap and containment before the run starts. There is no inherited individual or global learned policy; **every probability weight begins neutral (zero)**.
- After generation zero, *all 25 compete equally* regardless of whether the initial shape was constructive or stochastic. The initial source is kept in the audit log, but is **never part of the selection score**. A nonconstructive shape can take any selection slot, and its descendants have no protected source quota.

## Evolution and selection

- 25 parents per generation, 5 attempted offspring each: **125 proposals per generation / 37,500 over 300 generations**.
- Adaptive relative-credit policy learns action/size/direction; raw and local-compression improvement and geometry-check costs are accounted separately.
- Valid endpoint geometries only; local compression on valid raw offspring; no overlap in accepted parents.
- Stagnation control: normal => precision from 40 no-record generations => escape from 80 => diversify from 120, plus independent slow rolling-window progress signals.
- Selection targets 16 quality + 7 competitive near-best diversity + 2 broad exploration in normal mode; diversify uses 13 + 9 + 3. These are **roles**, *not* categories of initial origin. The diversity score includes a side-length penalty, limiting waste on extremely poor packings.
- The strict best-ever result is archived, even if no selected survivor would otherwise retain it.

The fraction of valid offspring is *not* proof of progress. For 12 squares, the known constructive upper bound is L=4 and an improvement would require an independently validated result **L<4**. An unchanged record after 300 generations does not prove optimality.

## Outputs

`results/fresh12-p25-g300/` contains:

- `initial_population.json`: exact 25 initialized geometries and tags; `config.json` records the fresh-start protocol.
- `generations.jsonl`, `generations.csv`, `individuals.jsonl`, `selection.jsonl`: complete history, candidate lineages, operator feedback and survivor decisions.
- `generation_images/`: **301** full 25-member images, generations 0–300.
- `run_summary.json`, `best_result.json`, `selected_population_final.json`, `verification.json` for final scoring and audit.
- `best.png`, `start.png`, `middle.png`, `final.png`, `progress.png`, `source_code/`, `complete.zip`, `generation_images.zip`.

To change the seed without introducing prior training:

```powershell
py -3 scripts/run_fresh_25.py --squares 12 --population 25 --structural-seeds 7 --generations 300 --seed 2716 --output-dir results/fresh12-p25-g300-seed2716
```

This is a new independent run, not a continuation. Use matched seeds and geometric-check budgets for controlled comparisons. The historical continuation runners remain available but are not used by this command.

## October 2026 archive audit and independent-init improvement

A complete, independently started 300-generation test (`seed=2715`) ended at
`L=4.0`, with 20,971/37,500 valid children, 2,970 children better than their
*own parents* but no globally improved record. Reconstructing every parent ID
from the archived `individuals.jsonl` showed that already in generation 1,
22/25 selected genomes descended from the seven constructive seeds. By
end-generation 300, 22/25 selected genomes still descended from those seeds;
only three `random_sparse` lineages survived. Most of the former stochastic
initializers had side length above 4.34 and the rigid/tilted variants were
based on the very same canonical grid.

**Initializer update (applies only to subsequent runs):** the stochastic slots
now use a bank of *distinct constructed silhouettes* as their geometric starting
points, with mild rigid tilts and modest individually rotated/perturbed layouts
near the `ceil(sqrt(n))` reference; occasional sparse wide explorers remain.
For the standard n=12, 25-parent case, the reproducible initial mix is 7
constructive + 9 rigidly rotated + 6 individually perturbed + 3 sparse.
In a one-generation preflight using seed 2715, six stochastic-origin lineages
survived selection versus three in the historical archived run. This is a
**one-generation diagnostic only**; it does not establish better long-run
record performance. Every shape is validated and no past results are inherited.

The fresh runner now reports `initial_origin_breakdown`,
`competitive_stochastic_initial_count`, and `final_ancestry_counts` in
`run_summary.json`, includes `selected_ancestry_counts` in per-generation logs,
and tags final genomes with `initial_ancestor_source`. **Selection ignores all
of these labels**; they exist solely to measure population collapse, without
introducing fixed ancestry quotas or preferences.

For a subsequent *separate* long-run experiment, retain the old directory
for a fair baseline and use a new directory:

```powershell
py -3 scripts/run_fresh_25.py --squares 12 --population 25 --structural-seeds 7 --generations 300 --seed 2715 --output-dir results/fresh12-p25-g300-initv2
```

Run one seed only for exploration; compare several matched seeds and equal
geometry-check budgets before claiming the revised initialization performs
better. Do not attribute constructive generation-zero L=4 to evolution.