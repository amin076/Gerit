# Historical-only stagnation experiment (2000 generations)

This is a new **opt-in** population-management policy in the generic Gerit
engine. It does not change the original V1 or fair-budget V2 branches.

**Interpretation:** "Historical only" means all newly created *population
lineages* after a stall come from archived historical states. Each living
lineage still creates ordinary trial children inside itself to make progress.
One live forward champion is retained. On a full population, no branch is
spawned until an eligible historical trial expires or contracts.

## Control policy
- `--historical-only-on-stall --adaptive-historical --fair-historical-budget`.
- Start with one forward lineage; allow up to nine historical lineages in a
  population of ten. No regular `_add_branch` or temporary `_spawn_explorer`.
- A stall is two consecutive weak progress checks by default. Spawn a single
  historical lineage no more often than once each 60 generations (adjustable).
- Choose checkpoints from the spaced historical archive with rollback within
  80–1500 generations. Candidate ranking favors a target age from nine
  evenly spaced lookback targets, while rewarding novelty and state quality.
  This balances *ages*, but does not guarantee uniform coverage of solution
  geometry. No archive younger than the minimum can be selected.
- Use V2's depth-related protected trial budget and incremental extensions
  for measurable progress. Promoted historical lineages can replace the
  single forward champion if they demonstrably beat it.
- A progress-triggered contraction can remove **one eligible historical**
  branch after its protected period, not the sole forward champion. At the
  full capacity, further historical spawns are deferred until room exists.
- All historical birth/expiry/promotion and best-record events are in
  `run_summary.json`; real node ancestry is in `genealogy.jsonl`.

## Commands (Windows CMD, from C:\\Physics\\Gerit\\gerit_core_v1)

Run the tests first:
```bat
py -3 -m unittest discover -s tests -v
```

Then the full experiment, starting from the same immutable geometry as
the earlier 4534 runs (not a later winner):
```bat
py -3 -u -m examples.square_packing ^
 --square-count 18 --iterations 2000 ^
 --initial-state results\\squares-18-warm-2000-4533\\best.json ^
 --initial-parents 1 --max-parents 10 ^
 --max-forward-branches 1 --max-historical-branches 9 ^
 --adaptive-historical --fair-historical-budget ^
 --historical-only-on-stall --historical-forward-reserve 1 ^
 --historical-lookback-min 80 --historical-lookback-max 1500 ^
 --historical-spawn-interval 60 --historical-stall-windows 2 ^
 --historical-trial-generations 300 --historical-depth-budget-ratio 0.75 ^
 --historical-max-trial-generations 1200 ^
 --historical-progress-extension 100 --historical-progress-window 100 ^
 --historical-min-progress-fraction 0.00001 ^
 --historical-archive-interval 20 ^
 --children-per-parent 10 --population-adjust-interval 20 ^
 --reservoir-size 128 --evaluation-budget 350000 ^
 --compression-attempts 4 --rotation-attempts 12 ^
 --operator-set legacy-hybrid --log-every 10 --checkpoint-every 10 ^
 --lineage-video --fps 30 --image-width 900 --seed 4534 ^
 --output-dir results\\squares-18-historical-only-2000-4534
```

Short smoke check: change only iterations to 100 and output directory to
`results\\historical-only-smoke`. Note: with rollback minimum of 80 and
spawning interval of 60, a smoke run may not create many historical lineages.
Check progress and events after a few hundred generations.

## Comparison limits
A 2000-generation run is not directly comparable to the old 2330-generation
endpoint, and varying active population changes the number of evaluations per
generation. Compare the best L at **equal evaluation counts**, and record all
lineage-spawn and rollback events. The same RNG seed is not identical random
draws once code paths diverge.

The assistant has committed the changes but has not executed the user's
Windows tests or a full packing run. The 2000-generation run is user initiated.
