# Fresh four-branch multi-seed reproducibility + historical provenance

This experimental branch preserves the original population policy:
18 unit squares, independent 8x8 GRID initial placement, 1 initial lineage,
at most 4 total (2 forward + 2 historical), 3000 generations. It changes
**logging and audit attribution**, not population ratios.

## Run (Windows CMD)

From the Git repository root:
```bat
git fetch origin
git switch --track origin/experiment/provenance-multiseed
cd gerit_core_v1
py -3 -m unittest discover -s tests -v
run_fresh_four_branch_multiseed.cmd
```

The batch runs five sequential new experiments with seeds
4536, 4537, 4538, 4539, 4540. It does not supply `--initial-state` or
warm-start any prior outcome. Each run is isolated in
`results/squares-18-fresh8-p4-g3000-SEED`. Existing seed 4535 is included
in the CSV summary without rerunning it.

To regenerate just the report:
```bat
py -3 -m examples.summarize_multiseed --results-root results --include-seed 4535
```

Report: `results/four_branch_multiseed_summary.csv`.

## Attribution
Each evaluated candidate records the historical origin (if any) inherited
from the actual parent lineage active when it was generated. This metadata
is saved to genealogy nodes and best-record event origins, and carries into
child population lineages even if they are later promoted to `forward`.
The true node parent link remains independent of population labels.

A branch seeded from a historical state need not be causally descended from
the nearest *geometric* active parent. This implementation derives new
lineage provenance from the seed candidate itself, not from geometric
nearest-neighbor parent selection. Historical branch resurrection explicitly
starts a new historical provenance identity. This avoids false attribution
due only to similarity.

**Important experimental limits**: Historical provenance is a recorded
genealogical association, not causal evidence that disabling historical
restarts would make the solution impossible. One prior run (4535) was
completed before these added provenance fields and will have absent or
zero attribution metadata; do not interpret those missing fields as proof
of no historical ancestry. Compare final L distributions and the same
evaluation-count checkpoints to infer repeatability. Different seeds with
identical grid geometry test random trajectory variability, not sensitivity
to initial geometry. Separate ablation runs disabling historical branching
are needed to infer that feature's causal effect.

No full run or test execution was performed in GitHub by this change.
