# L-frame recursive scan across all 1,000 problems

The L-frame is a constructive, non-evolutionary transformation. It takes
an existing validated packing of N unit squares with axis-aligned bounding
side L and appends two straight strips (top and right) plus the far corner.

Let k=floor(L). Then, for **any** feasible source:

- Target count: N'=N+2*k+1
- Constructed side: approximately L'=L+1+1e-6 (small certified clearance)
- Target accepted only when a **strict/interval SAT valid** pose beats its
  currently saved champion in the 1,000-solution registry.

When N=k0²+1 and L between k0 and k0+1, the new target is
(k0+1)²+1. For k0=2..31 that is the 30-count family:
5,10,17,26,37,50,65,82,101,122,145,170,197,226,257,290,
325,362,401,442,485,530,577,626,677,730,785,842,901,962.

**Distinction:** the 30-count sequence is only a special expected chain.
The actual script loops over EVERY N from 1 to 1000 and uses whatever
packing is currently stored at N, including improvements generated earlier
in the same sweep. It can discover other target counts if feasible.

## Commands for Windows CMD

First update the exact existing branch:

```cmd
cd C:\Physics\Gerit
git branch --show-current
git pull --ff-only
py -3 -m unittest tests.test_l_frame_propagation -v
```

For a **dry run that cannot alter the registry**, including chained
hypothetical improvements:

```cmd
py -3 scripts/run_l_frame_propagation.py --report results/kaggle_l_frame/dryrun.json --ledger results/kaggle_l_frame/dryrun_ledger.jsonl
```

Then, after checking the candidate N values and score, apply only
independently certified improvements:

```cmd
py -3 scripts/run_l_frame_propagation.py --apply --report results/kaggle_l_frame/applied.json
py -3 scripts/kaggle_best_registry.py status
```

The script prints each transition N->N', the previous and new L, full
ancestry chain, and the final list of accepted targets. It also saves a
JSON report, a machine-readable CSV summary, and method-ledger entries
for full algorithm provenance. Each report path is write-once; choose a
new path for repeat experiments. Registry changes are applied sequentially
and atomically; do not run concurrent --apply jobs.

The CI workflow `Gerit L-frame 1000-screen` runs both dry-run and apply
against a **disposable** registry with the existing 15 center-45 examples,
then exports a complete independently verified Kaggle submission CSV.
It does not replace the user's local registry and does not upload anything
to Kaggle.

Every result is a valid construction if certified; it is not an optimality
proof, and the number of improvements depends on the current bank.
