# Automated Gerit half-interval campaign

Use ONE command instead of typing separate growth and deep-compression
commands for hundreds of consecutive problems. This is a local Python
runner (Windows CMD), **not** an always-running ChatGPT automation or a
GitHub-hosted unlimited compute service.

## Exact selection rule

For a square-grid interval k^2 ... (k+1)^2 there are 2k
*interior* problem counts: k^2+1 ... (k+1)^2-1. The
first half is exactly:

    N = k^2+1, k^2+2, ... k^2+k

Examples:

- 15^2=225 -> 16^2=256: N=226..240 (15 counts);
  if starting at 231, visit 231..240 (10 new counts).
- 16^2=256 -> 17^2=289: N=257..272 (16 counts).
- 17^2=289 -> 18^2=324: N=290..306 (17 counts).

The campaign skips the second half of each interval, **not** because
those cases are impossible, but because this was the requested initial
sampling strategy. The --max-n limit may reach N=1000.

## Fixed invalid JSON file from earlier N231 growth

Early versions of run_elastic_repair.py wrote the two literal characters
backslash+n after the closing brace of best-file JSON, causing Python's
`JSONDecodeError: Extra data`. The writer now emits a real newline.
`gerit.packing_io.load_packing_json` can safely parse the legacy
file if and only if the unexpected suffix consists exclusively of
literal backslash+n sequences and whitespace. Other extra content is
rejected. **Coordinates are not edited and the geometry must still
pass the strict and independent interval SAT checks.**

After `git pull`, this original command can be reissued with a NEW
experiment folder, even if the preexisting best-file JSON is old:

```cmd
py -3 scripts/run_deep_elastic.py --n 231 --candidate-file results/kaggle_elastic_growth/n231_from_deep230_s105_best.json --generations 900 --iterations 180 --seed 2310 --output-dir results/kaggle_deep/n231_g900_s2310_fixed
```

You do **not** have to run that manual command if using the automatic
campaign below. If `n231_g900_s2310` was not created by the failed
command, that original directory name is also usable.

## Start a 10-problem local pilot: N231 to N240

```cmd
cd C:\Physics\Gerit
git switch feature/gerit-1000-integrated
git pull --ff-only
py -3 -m pip install -r requirements.txt
py -3 -m unittest tests.test_auto_family_sweep -v
py -3 scripts/run_auto_family_sweep.py --first 231 --max-n 240 --attempts 10 --iterations 250 --deep-generations 10 --deep-iterations 100 --seed 20261112 --output-dir results/kaggle_auto/pilot231_240
```

When N231 is first, the engine tries to use the existing
`results/kaggle_deep/n230_g900_s2300/best_valid.json` as its founder
**only after independent certification** and only if that side is better
than the saved bank's N230. Otherwise it uses the independently
certified bank solution.

For each target N:

1. Start from the best certified N-1 packing (virtual dry-run winner
   from the previous step if better than registry, otherwise registry).
2. Add one square and run ten independently seeded SAT-based growth
   attempts with escalated collision penalties.
3. Save any independently certified best growth candidate.
4. Run ten generations of fixed-N deep compression from that result,
   or from the valid grid/bank if growth failed.
5. Keep the smaller independently certified output and use it as the
   founder of N+1. If none beats the bank, use the existing certified N
   registry solution. Do not stop the campaign for a single failure.
6. Write a durable JSON checkpoint to
   `results/kaggle_auto/pilot231_240/sweep_state.json`.

The default is **dry-run**. It does not edit the 1000-case registry.

To resume after a clean stop at a per-N checkpoint or an interrupted
generation, run THE SAME command with `--resume` appended. The
system avoids overwriting earlier files and can retry partial stages
in fresh folders.

## Automatic full-range campaign

For the requested first halves of successive square intervals all
the way through N1000:

```cmd
py -3 scripts/run_auto_family_sweep.py --first 231 --max-n 1000 --attempts 10 --iterations 250 --deep-generations 10 --deep-iterations 100 --seed 20261112 --output-dir results/kaggle_auto/full231_1000
```

You may use `--apply` for verified automatic best-bank updates, but
run ONLY ONE writer to that registry at a time and verify that the
pilot behaved as intended before enabling automatic mutations.
`--resume` requires identical settings including `--apply`, so a
dry-run campaign should not later be resumed as an apply campaign.
Saved candidates may instead be evaluated and registered separately.

## Computational limitations

The 10 attempts plus 10 deep generations are a **minimum exploration
budget**, not ten evolutionary generations of the original Gerit
algorithm. Each attempt can include hundreds of internal SciPy
iterations. This sweep may use substantial CPU time for large N.
There is no promise of a globally optimal packing nor a guarantee that
every N will improve. The main Gerit evolutionary optimizer,
historical jumps, registry archive and existing Kaggle CSV remain
unchanged unless an `--apply` update passes the independent verifier.
