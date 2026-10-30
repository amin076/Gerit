# Gerit fair historical branch budget — experimental

Based on prior baseline run 4534 (L=5.054600108145, 199775 evaluations,
2341 generations) and historical run 4534 (L=5.027699620483,
138072 evaluations, 2330 generations).

## Motivation
Historical lineage #32 created records near generations 1592–1616, yet was
expired at 1620 because the old controller checked current state after uphill
exploration, not best-so-far performance. This version tracks a separate
best-so-far candidate for every historical lineage and uses it for promotion,
expiry comparison, and fairness.

## Policy (opt in)
- `--adaptive-historical --fair-historical-budget`
- Interleave historical spawns once a small forward reserve exists; do not
  require five forward branches first.
- A historical seed rollback distance D receives at least
  `max(historical_trial_generations, ceil(D*historical_depth_budget_ratio))`
  protected generations, capped at `historical_max_trial_generations`.
  This is a *heuristic resource rule*, not a theorem of fairness.
- At the end of each historical progress window, if best-so-far gain relative
  to the previous checkpoint exceeds `historical_min_progress_fraction`,
  extend the protected trial by `historical_progress_extension`, subject to
  the hard cap. A current global-best contributor may receive extension too.
- If the historical branch is ready for promotion, its best archived candidate
  rather than its latest exploratory position becomes the new forward seed.
- On population contraction, remove an eligible forward branch first,
  retaining at least one forward branch; protected historical branches cannot
  be cut early. Historical branches are expired / promoted separately.
- Existing global best `best.json` is never replaced by a worse candidate.
- No nested Search or multiple engines; one population loop with independent
  lineage budgets. The per-branch trial duration is measured in global
  generations; actual evaluation allocations depend on parent count.

## Example for controlled experiments
From `C:\\Physics\\Gerit\\gerit_core_v1`, first run tests:

```bat
py -3 -m unittest discover -s tests -v
```

Then (same exact initial geometry as earlier experiments):

```bat
py -3 -u -m examples.square_packing ^
 --square-count 18 --iterations 2330 ^
 --initial-state results\\squares-18-warm-2000-4533\\best.json ^
 --initial-parents 1 --max-parents 10 ^
 --max-forward-branches 3 --max-historical-branches 7 ^
 --adaptive-historical --fair-historical-budget ^
 --historical-forward-reserve 2 ^
 --historical-depth-budget-ratio 0.75 ^
 --historical-max-trial-generations 1200 ^
 --historical-progress-extension 100 ^
 --historical-progress-window 100 ^
 --historical-min-progress-fraction 0.00001 ^
 --historical-lookback-min 100 --historical-lookback-max 1500 ^
 --historical-trial-generations 300 --historical-spawn-interval 100 ^
 --historical-archive-interval 20 --historical-stall-windows 2 ^
 --children-per-parent 10 --population-adjust-interval 20 ^
 --reservoir-size 128 --evaluation-budget 350000 ^
 --compression-attempts 4 --rotation-attempts 12 ^
 --operator-set legacy-hybrid --log-every 10 --checkpoint-every 10 ^
 --lineage-video --fps 30 --image-width 900 --seed 4534 ^
 --output-dir results\\squares-18-fair-historical-2330-4534
```

For an attribution audit of an already completed run:

```bat
py -3 -m examples.analyze_historical_ancestry ^
 --output-dir results\\squares-18-historical-2330-4534
```

**Not proved yet**: this scheme may or may not improve any packing run.
Compare the best objective at *equal evaluation counts* across many independent
seeds. Use a three-arm ablation: legacy, first historical controller, and
fair-budget controller. Do not treat matching RNG seeds across changed
control flow as identical random samples.

Caveat: no Python suite or multi-thousand-generation search was executed by
the assistant; run tests and a short smoke test locally first.
