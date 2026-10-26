# Gerit v4 — rolling-progress escape and measurable attribution

Adaptive v4 **preserves** the original v3 run (`scripts/run_adaptive.py`) and its relative-credit learning policy, geometry, compression and elite archive. It adds a new runner (`scripts/run_adaptive_v4.py`) plus rolling-progress detection (`gerit/adaptive_v4.py`).

## Continue from the user's Round 20 on Windows

From `C:\Physics\Gerit`, first `git pull --ff-only`, then:

```powershell
py -3 -m unittest discover -s tests -v
py -3 scripts/run_adaptive_v4.py --input results/round20-adaptive/selected_population_final.json --generations 300 --seed 2611 --output-dir results/round21-adaptive-v4
```

No new package dependencies. **Use a fresh `--output-dir`**; the runner refuses to overwrite runs.

## What changes

- Best-known side over an exact trailing **80 completed generations**, including the starting snapshot, is compared with a threshold of **0.0001** units. The threshold is an experimental default, not a theoretically proven value.
- Only a **full window** is evaluated. Incomplete histories are not assumed to be stagnant.
- If the last 80 generations improved by less than the threshold for 1 successive end-of-window observation, precision is activated. After **20** consecutive weak windows, `escape` becomes active; after **60**, `diversify` becomes active. The more aggressive of this signal and the old idle-generation signal wins. Substantive recent improvement resets the *weak-window streak*.
- The old 40/80/120 idle-generation thresholds remain as a fallback and are separately recorded. An isolated +0.000002 record does not necessarily reset the new progress-window signal.
- On resuming from a v3 run like Round 20, the new runner reads adjacent `generations.jsonl` to reconstruct trailing 80-generation progress when that file is present. Without it, starts a fresh window instead of fabricating history. On resuming v4, the compact window and low-progress streak are persisted directly inside `selected_population_final.json`.
- `mode_metrics.json` and `run_summary.json` include proposals, accepted children, direct improvements, improvements relative to parent after compression, geometry-validator calls, global record events and record gain **attributed to the active mode**. Record improvement is counted when a selected new elite beats the previous record by more than `1e-10`; this is separate from meaningful-record `1e-6` signals. Operator-level record contribution and new selected births are also tracked. `generations.jsonl`/`.csv` log `rolling_window_gain` and `rolling_weak_streak`.
- The best valid elite is still preserved. A known 4x3 grid is **not** injected. No guarantee of improvement or superiority without matched-seed, matched-check evaluations.

## Optional experimental tuning

```powershell
py -3 scripts/run_adaptive_v4.py --input results/round20-adaptive/selected_population_final.json --generations 300 --seed 2612 --output-dir results/round21-v4-alt --window-generations 80 --min-window-gain 0.00005 --slow-precision-after 1 --slow-escape-after 20 --slow-diversify-after 60
```

The `--precision-after`, `--escape-after`, `--diversify-after`, and `--significant-gain` arguments still control the v3 idle-based fallback. Compare variants from the **same original input** and using geometric-validation budgets, not generations or accepted-child count alone.