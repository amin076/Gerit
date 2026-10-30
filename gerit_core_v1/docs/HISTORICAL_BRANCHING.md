# Adaptive Historical Branching — experiment (opt-in)

This experiment adds deep, protected historical exploration to the **generic**
Gerit engine without square-packing logic in the core. The original branch
`experiment/single-lineage-video` is the untouched baseline.

## Behaviour
- Off by default (`--adaptive-historical`). Default capacity: five forward
  branches and five historical branches within the global maximum of ten.
- A bounded, spaced historical archive saves actual selected parent states
  every 20 generations, separately from the short rolling snapshot buffer.
- The controller detects consecutive weak 20-generation progress windows.
  Forward branches grow normally to five; further weak windows may create
  one historical branch every 100 generations, if an eligible historical
  checkpoint exists.
- The checkpoint must be 100–1500 generations old and structurally distinct
  from live branches. Selection weights are structural novelty (0.5), age
  (0.3), and candidate quality (0.2). These are per-candidate normalized
  values; they are NOT predictions of long-run success.
- Historical seeds bypass the ordinary current-best `absolute_regression`
  filter. They receive independent step-size learning, increased operator
  exploration and jump probability, and a bounded allowance for uphill
  intermediate steps.
- They are protected from population contraction for 300 generations.
  Afterwards, a branch is either promoted to an available forward slot if
  competitive or expired so its budget can be reused. The best-ever state
  remains archived independently.
- Events `historical_spawn`, `historical_promote`,
  `historical_expire`, and `historical_shortfall` provide auditability;
  `historical_stats` and archive size are in status/summary JSON.
- Existing `--lineage-video` uses exact selected-state `node_id` /
  `parent_node_id` links, including backtracked branches.

## Fair experiment
To compare with the ongoing baseline run 4534, start from the SAME immutable
geometry as that run (the final `best.json` of run 4533). Do not warm-start
from 4534's latest state or the comparison would not measure the new policy.
The run has a fresh RNG, operator-learning memory, and generation counter
because warm-start restores geometry only.

On Windows CMD, from `C:\\Physics\\Gerit\\gerit_core_v1`:

```bat
py -3 -m unittest discover -s tests -v
py -3 -u -m examples.square_packing ^
 --square-count 18 --iterations 3000 ^
 --initial-state results\\squares-18-warm-2000-4533\\best.json ^
 --initial-parents 1 --max-parents 10 --children-per-parent 10 ^
 --population-adjust-interval 20 --reservoir-size 128 ^
 --evaluation-budget 350000 --compression-attempts 4 ^
 --rotation-attempts 12 --operator-set legacy-hybrid ^
 --adaptive-historical --max-forward-branches 5 ^
 --max-historical-branches 5 --historical-lookback-min 100 ^
 --historical-lookback-max 1500 --historical-trial-generations 300 ^
 --historical-spawn-interval 100 --historical-archive-interval 20 ^
 --historical-stall-windows 2 --log-every 10 --checkpoint-every 10 ^
 --lineage-video --fps 30 --seed 4534 ^
 --output-dir results\\squares-18-historical-3000-4534
```

Do not run this in the baseline output folder. Compare **best side L against
evaluation count**, not only generation count. If the original run is stopped
early, compare at the common evaluation budget and record the early stop.
The two policies may diverge in evaluation count and RNG call order.

## Limitations
- This prototype has not been proven to improve 18-square packing.
- Archive keeps a representative of each time slice, not all discarded
  children; memory and archive capacity are bounded.
- Any genealogy begins at the warm-start root of the current run, not in
  previous runs that did not record true parent links.
- Tests should run on the user's machine before a long experiment.
