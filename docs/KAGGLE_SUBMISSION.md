# Gerit — Kaggle Squares in Squares integration

This integration extends the existing Gerit repository. It does not replace
the evolutionary optimizer or edit historical experiments.

Competition: https://www.kaggle.com/competitions/squares-in-squares
Data/schema: https://www.kaggle.com/competitions/squares-in-squares/data
Official metric: https://www.kaggle.com/code/metric/squares-in-squares/output

## Repository audit

The solver uses gerit/geometry.py for rigid unit squares, gerit/evolution.py
for mutation and selection, adaptive/learned policies for stagnation escape,
scripts/ for continuation and fresh experiments, and results/ for audit logs.
The repository contains 20 saved N=12 individuals at
data/round15_selected_population_final.json. The best reported side is
4.006477636998101, slightly WORSE than the valid N=12 4-by-3 grid (L=4).
We retain it as experimental evidence, but do not replace the grid with it
in the full competitive submission.

The README states that later round18 results reside on the user's Windows
machine and are absent from GitHub. The five-square configuration is not a
solution. References to N=17 experiments do not establish stored coordinates.

## Official scoring and submission

Each feasible N has score L/sqrt(N)-1. For missing/invalid N, Kaggle assigns
ceil(sqrt(N))/sqrt(N)-1. The total sums all N from 1 to 1000.
The full grid-only baseline score is 28.937669916550586.

Official CSV columns, in order: id,n,square_id,x,y,angle.
IDs are sequential 0..row_count-1; square_id is 0..N-1 within each N.
Each N included must have exactly N centers and rotation angles in radians.
Coordinates are decimal text, not symbolic expressions. Full export is
500500 data rows plus a header.

The independent verifier uses interval-arithmetic rotated-square SAT with
escalating precision (50,100,200,500 digits) and rejects uncertifiable contact.
Exact integer-lattice grid candidates use an exact fast-path. A scalar L with
no saved poses is not a feasible candidate. Full export chooses only validated
Gerit improvements over grid; partial export includes any validated Gerit
packing, even if its L exceeds the grid benchmark.

## Windows PowerShell instructions

    cd C:\Physics\Gerit
    git fetch origin
    git switch feature/kaggle-submission-pipeline
    py -3 -m pip install -r requirements.txt
    py -3 -m unittest discover -s tests -v
    py -3 scripts/kaggle_submission.py --sources data results --out kaggle_output --full-recheck

Outputs:

- kaggle_output/submission_complete.csv: grid + improved Gerit poses for N=1..1000.
- kaggle_output/submission_partial.csv: validated Gerit-only poses.
- kaggle_output/competition_report.json: per-N scores and complete audit inventory.
- kaggle_output/competition_report.csv: readable per-N comparison.

The complete file is the initial recommended upload. Go to
https://www.kaggle.com/competitions/squares-in-squares/submissions
and use Submit Predictions with kaggle_output/submission_complete.csv.

To scan historical runs kept only on your own PC without copying/overwriting
their source files:

    py -3 scripts/kaggle_submission.py --sources data results\round18 results\fresh12-p20-g1000 --out kaggle_output --full-recheck

This scanner understands best.squares, selected_members, members and root
squares JSON structures. L-only summaries are recorded as incomplete.
Existing result trees are never overwritten.

The reference leader score 22.0544214515 comes from the user's screenshot
dated November 10, 2026; it is NOT a live leaderboard value. A projection
is NOT a confirmed Kaggle acceptance. Only an actual Kaggle upload and scoring
response can confirm that.

## Optimization after first accepted upload

Prioritize attainable delta(L/sqrt(N)), not N alone. Harvest saved real poses,
then estimate expected score gain, compute cost and reuse of constructive
seeds. Benchmark local contact optimization, annealing, multi-start and
evolutionary continuation with matched budgets before integrating any changes.
Never discard historical archives or infer missing coordinates.
