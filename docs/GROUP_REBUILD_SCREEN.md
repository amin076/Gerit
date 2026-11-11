# Gerit group rebuilding: break local clusters, rotate, add a square

Earlier `free_space_insert` evaluated 149,223 single-pose probes
with ALL previous squares fixed; it did not improve the current 30-answer
bank. This experimental follow-up removes `k` squares, holds the
remaining N-k in place, and searches for `k+1` valid placements. All
square angles are free within the enumerated {-45,-30,-15,0,15,30,45}
degrees, and their centers may move. Candidate clusters can be spatially
local or selected as several separate squares (long-range jump).

This does **not** modify or replace the existing advanced Gerit
evolution engine, its historical-jump population logic, or the 1,000-case
registry. It is a separate neighborhood search. The full saved answer is
always strictly and independently SAT-validated before any replacement.

The CI run recreates all thirty earlier solutions in a disposable bank,
then performs the screen for N < 120 (the cheaper pilot). The default
local run also uses `--max-n 120`. Increase to 1000 only after reviewing
the pilot, and use smaller attempt budgets at large N. A lack of improvement
is NOT proof that no packing exists.

## Windows CMD - dry run

```cmd
cd C:\Physics\Gerit
git pull --ff-only
py -3 -m unittest tests.test_group_rebuild_screen -v
py -3 scripts/run_group_rebuild_screen.py --max-n 120 --attempts 60 --probes 50 --group-size 3 --report results/kaggle_group_rebuild/pilot.json
```

`accepted_count`, `accepted`, `initial_score` and `final_score`
are in the JSON report. Dry-run preserves the archive but records the
candidate discovery in its method ledger. The previous answer score
28.077128574899618 is the benchmark for comparison.

If this pilot shows certified improvements, apply with a **distinct**
report filename:

```cmd
py -3 scripts/run_group_rebuild_screen.py --max-n 120 --attempts 60 --probes 50 --group-size 3 --apply --report results/kaggle_group_rebuild/pilot-applied.json
py -3 scripts/kaggle_best_registry.py status
```

To broaden the scope to the full 1000 once the pilot is tested:

```cmd
py -3 scripts/run_group_rebuild_screen.py --max-n 1000 --attempts 25 --probes 30 --group-size 4 --seed 20261113 --report results/kaggle_group_rebuild/full-dryrun.json
```

Use a different `--seed` and report path for each repeat. Historical
report paths are write-once. Only one registry writer should run at a
time. Every promising candidate is attributed to
`group_rebuild_plus_one` in `results/kaggle_method_ledger.jsonl`,
including seed, k, probing budget, source and destination N.
