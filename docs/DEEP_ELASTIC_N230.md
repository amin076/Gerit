# Gerit: deep compression of the certified N230 record

The first valid 230-square packing (local archive reported
L=15.999408328109391, total score 28.070173371732) is a **starting
point**, not a stopping condition. The operator introduced here searches
for much smaller values than 16, without changing Gerit's existing
historical-jump evolutionary engine or the certified 1000-case archive.

## What changes

- Fixed N=230 throughout a run. No square is added during this phase.
- All square centers and all angles are variables in the SAT-based
  continuous relaxation.
- Five mutation families: collective compression; local cluster moves;
  distant multi-square jumps; global Gaussian perturbations; and
  local-group rotation/translation.
- A graduated target side (0.000025 to 0.035 smaller than the incumbent)
  and increasing overlap/boundary penalties.
- Best independently interval-certified packing is preserved in the
  experiment folder even on runs that end with zero updates. An
  unsuccessful near-feasible attempt is checkpointed separately.
- Progress prints every 10 generations by default. Runs can use
  hundreds or thousands of generations.
- --apply updates the existing registry **only when independently
  certified solutions are strictly better**. Grid solutions and past
  records remain intact; archive is never reset.

## Commands — Windows CMD

Check out the feature branch, then pull new code:

```cmd
cd C:\Physics\Gerit
git switch feature/gerit-1000-integrated
git pull --ff-only
py -3 -m pip install -r requirements.txt
py -3 -m unittest tests.test_deep_elastic -v
py -3 scripts/kaggle_best_registry.py status
```

Start the first 900-generation experimental run without changing the
1000-case registry:

```cmd
py -3 scripts/run_deep_elastic.py --n 230 --generations 900 --iterations 160 --seed 2300 --log-every 10 --shrink-max 0.035 --output-dir results/kaggle_deep/n230_g900_s2300
```

Inspect `results/kaggle_deep/n230_g900_s2300/progress.json`,
`best_valid.json`, and `best_near.npz`.
A certified improvement prints `CERTIFIED gen=...`.

Continue from the previous experiment's **best certified and best
near-feasible** snapshots with a fresh budget and seed:

```cmd
py -3 scripts/run_deep_elastic.py --n 230 --generations 900 --iterations 180 --seed 2301 --resume-dir results/kaggle_deep/n230_g900_s2300 --output-dir results/kaggle_deep/n230_g900_s2301
```

After checking the improvement, a new **--apply** run may register
certified improvements as it goes. For safety, do not run any other
registry writer at the same time:

```cmd
py -3 scripts/run_deep_elastic.py --n 230 --generations 900 --iterations 180 --seed 2302 --resume-dir results/kaggle_deep/n230_g900_s2301 --output-dir results/kaggle_deep/n230_g900_s2302_apply --apply
py -3 scripts/kaggle_best_registry.py status
```

Do not submit a new Kaggle CSV unless a certified score improvement is
confirmed and the complete export passes the existing independent
validation.

After deep compression, the next N=231 solver uses the updated N230
archive in the **existing** growth/repair workflow:

```cmd
py -3 scripts/run_elastic_repair.py --n 231 --attempts 24 --iterations 500 --seed 105 --report results/kaggle_elastic_growth/n231_repair.json --checkpoint results/kaggle_elastic_growth/n231_nearest.npz
```

For a repeat of this command use fresh output paths: all experiment
folders and reports are intentionally non-overwriting.

## Caveat

A run with a large generation budget can still stagnate. Each
generation contains several nonlinear optimizations. Increasing the
budget increases the search opportunity but does not prove any specific
score or guarantee an improvement. The GitHub Actions CI checks
**software safety on small test problems**; the long N230 search is run
on the user's own best archive, not automatically on GitHub.
