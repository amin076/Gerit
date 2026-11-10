# Three sequential square-packing trials (N=17, 18, 19)

This experiment uses **the unchanged `gerit.evolution.evolve` engine** with
20 parents, 5 offspring per parent, 75% fitness selection / 25% diversity,
500 real generations for each N, and reports progress to CMD every 20
generations. The three N values run **sequentially**, not in parallel.

The geometric mutation wrapper is N-agnostic. Its 35% structural share
mixes contact compaction (40 attempts per call), pivot-release moves
(72 attempts per call), reconfiguration and contact relocation.
The original coordinated mutation still handles the remaining 65% of
offspring proposals. No optimal layouts or answer angles are injected.

## Running in Windows CMD

```bat
cd C:\Physics\Gerit
git switch feature/five-square-corner-center
git pull --ff-only
py -3 -u scripts/run_three_square_counts.py --generations 500 --report-every 20 --out-root results/n17-n18-n19-500
```

Expected terminal checkpoints: `N=17 GEN 0/500`,
`N=17 GEN 20/500`, ..., `N=17 GEN 500/500`;
then `N=18`, then `N=19`.

Output is never overwritten. Individual results live under
`results/n17-n18-n19-500/n17`, `n18`, and `n19`.
Each contains original Gerit audit logs and images in its own `run-*`
subfolder plus `experiment_summary.json` and `best_packing.json`.
The top-level `sequential_summary.json` records completed cases and
failure status should a later case fail.

## Reference-only best known results

- 17: 4.67553009360455 (Bidwell 1998)
- 18: 4.82287565553229 (Hämäläinen 1980)
- 19: 4.88561808316412 (Wainwright 1979)

Sources: https://squaremath.org/cases/17.html,
https://squaremath.org/cases/18.html,
https://squaremath.org/cases/19.html

These values are **comparison targets only**. Starting layouts are
independent constructive 5×5-grid subsets with side length 5,
so a 500-generation run is **not guaranteed** to beat any published result.
These are baseline tests of generalization rather than optimized
Kaggle submissions.

To smoke-test without committing to the full budget:

```bat
py -3 -u scripts/run_three_square_counts.py --generations 5 --parents 5 --offspring-per-parent 2 --report-every 1 --image-every 5 --out-root results/n17-n18-n19-smoke-local
```

GitHub Actions smoke suite:
https://github.com/amin076/Gerit/actions/workflows/n17-n18-n19-runner.yml
