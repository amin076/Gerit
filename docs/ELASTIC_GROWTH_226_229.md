# Elastic growth experiment: 226 -> 227 -> 228 -> 229

This is a dedicated follow-up to the failed fixed-gap and three-square
rebuild screens. For N=227 the founder is the saved **validated 226-square
packing** in Gerit's existing best-answer registry, not a new repository
or a replacement for the evolution engine.

The algorithm inserts one new square and lets **all N old squares move
and rotate**, rather than fixing surrounding squares. A staged
differentiable separating-axis (SAT) objective penalizes overlap and
boundary penetration. Temporary overlap is an optimization device only.
The final output must pass (1) Gerit's strict collision validator and
(2) the independent high-precision interval SAT validator before
updating the registry.

It uses NumPy and SciPy (both declared in requirements.txt). It is
stochastic but deterministic for fixed seed and same dependencies.
The initial seed is 100, with 16 starts, and prints progress after
every five starts. This is **NOT** a claim that 227 is globally optimal,
nor a proof that 228 or 229 can be packed below side 16.

## Windows CMD: update, test, run 227 in dry-run

```cmd
cd C:\Physics\Gerit
git pull --ff-only
py -3 -m pip install -r requirements.txt
py -3 -m unittest tests.test_elastic_growth -v
py -3 scripts/kaggle_best_registry.py status
py -3 scripts/run_elastic_growth.py --first 227 --last 227 --attempts 16 --iterations 400 --seed 100 --report results/kaggle_elastic_growth/n227_dryrun.json
```

The report has `outcomes[0].strict_valid`,
`outcomes[0].interval_valid`, `outcomes[0].best_side`, and the
projected total score. **Dry-run does not mutate any registry entry.**

If at least one independently valid solution beats the saved N227
champion, apply it and track precise provenance:

```cmd
py -3 scripts/run_elastic_growth.py --first 227 --last 227 --attempts 16 --iterations 400 --seed 100 --apply --report results/kaggle_elastic_growth/n227_applied.json
py -3 scripts/kaggle_best_registry.py status
```

Then attempt the next two independently or as one continuous run.
A continuous run reuses each newly validated best answer as founder for
the next number, so a successful 227 can help 228 and 229:

```cmd
py -3 scripts/run_elastic_growth.py --first 228 --last 229 --attempts 24 --iterations 500 --seed 101 --report results/kaggle_elastic_growth/n228_229_dryrun.json
```

For the first four problems in the proposed interval (226, 227, 228,
229), N226 already has a certified winner due to L-frame; so the
new experimental sequence begins with 227.

The archived `gerit-elastic-n227` GitHub Actions artifact contains
the certified 1000-problem CSV and report for its **isolated** bank
if the workflow succeeds. It never overwrites the user's local archive.

Do not submit anything to Kaggle until a full independently certified
registry export exists and the expected score is compared to the prior
official 28.0771285749 (if Kaggle accepted that submission).

## Confirmed first pilot (CI 43072644094)

GitHub Actions:
https://github.com/amin076/Gerit/actions/runs/43072644094

- Full CI conclusion: **success**.
- Founder: validated N226 packing, L=15.707120181187.
- N227 starting bank side: 16.0 (grid).
- 16 starts, seed 100, 400 iterations per penalty stage.
- Independently interval-SAT-certified N227 improvement discovered on attempt 3.
- New certified N227 side: **15.989307680427**.
- Bank improved problems: **30 -> 31**.
- Total projected score: **28.077128574900 -> 28.076418900724**.
- An independently reimported and verified complete 500,500-row Kaggle CSV was produced.
- These are results from a disposable CI registry, not mutations of the local Windows bank.
- Improvement is mathematically feasible as checked, but no global optimality claim.
- N228 and N229 remain separate experiments; run after synchronizing and applying N227 locally.
