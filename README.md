# Gerit — Adaptive v3 (stagnation escape + relative learning)

**Current recommended command for the completed `round18` experiment on your Windows PC:**

```powershell
cd C:\Physics\Gerit
git pull --ff-only
py -3 -m pip install -r requirements.txt
py -3 -m unittest discover -s tests -v
py -3 scripts/run_adaptive.py --input results/round18/selected_population_final.json --generations 300 --seed 2609 --output-dir results/round19-adaptive
```

The round18 result is on **your** machine, not in the GitHub repository. Do not
copy it back into the repository: `--input` reads it in place, preserving all
20 final geometries and per-parent learned policies. The archived starting best
reported from your round18 terminal is `L=4.005430701105233` (verify that the
actual JSON is the expected file). If you do not have that file, omit `--input`
to start from the bundled Round15 survivors instead.

**What is new in v3:**

1. `gerit/adaptive_v3.py` uses the version-2 **separate** raw-mutation reward,
   local-compression reward and SAT cost, but updates action probabilities by
   **relative advantage** versus an exponential moving baseline. It centers
   family, step-size and directional logits rather than clipping all families
   to `-5`. The import migrator centers previously saturated v2 genes to
   neutral without creating artificial preferences for newly added operators.
   It also gives limited extra credit for children competitive with the best
   known packing and for genuine global records.
2. Automatic **mode switching** after generations with no meaningful global
   best improvement (default threshold `1e-6` in side `L`):
   - `normal` (0–39 idle generations): original 10 learned operator families;
     selection **18 quality / 2 diversity**.
   - `precision` (40–79): 55% of proposed births use very fine movements
     (`1e-8` to `0.004`), the rest the learned standard operators.
   - `escape` (80–119): 42% multi-square structural relocations, 33% micro
     movements, the rest standard learned operators.
   - `diversify` (120+): 60% multi-square relocations, 15% micro movements,
     the rest standard operators; temporarily select **12 quality / 8 diversity**.
   A sufficiently large new best resets the idle counter. Modes/transition
   history are recorded in outputs, and the idle counter is inherited when
   continuing a previous v3 run.
3. The best valid solution has an **independent non-regressing archive**, even
   when exploratory selection changes. Structural attempts may disrupt a
   packing, but invalid geometry is **never** admitted as a valid child. No
   known 4×3 grid placement is secretly inserted: `L=4` is a separate known
   baseline, not an evolved result.
4. Original `scripts/run_continuation.py` is intentionally unchanged as the
   **v2 control** for fair comparisons. `scripts/run_adaptive.py` is the new
   v3 experiment. Prior v2 output files remain readable as inputs.

Options (all optional):

```powershell
py -3 scripts/run_adaptive.py --help
py -3 scripts/run_adaptive.py --input results/round18/selected_population_final.json --generations 300 --seed 2610 --output-dir results/round19-refine --precision-after 40 --escape-after 80 --diversify-after 120 --significant-gain 0.000001
```

For a **four-generation smoke test** that forces each escape phase to be
exercised, use new thresholds on a disposable result folder:

```powershell
py -3 scripts/run_adaptive.py --input results/round18/selected_population_final.json --generations 4 --seed 2701 --output-dir results/adaptive-smoke --precision-after 1 --escape-after 2 --diversify-after 3 --significant-gain 100
```

This is a behavior test, **not** a promise that adaptive v3 outperforms v2.
To establish improvement, compare multiple seeds at equal internal geometry
check budgets (not just equal numbers of child proposals); the structural
operator can be more expensive. Every run writes `generation_images.zip`,
`complete.zip`, and `selected_population_final.json`. Source outputs and
previous experimental archives are preserved.

---

## Earlier v2 local workflow (still supported for controlled comparisons)

# Gerit — evolutionary packing of rigid unit squares

Gerit searches for valid arrangements of rotatable, **unit-size squares** inside
an axis-aligned square container. The score is the enclosing side length `L`
(or, equivalently, its area `L²`). No overlapping interiors are permitted.

**Current local workflow:** continue the real 12-square experiment from the
**20 selected parents at the end of Round 15**, preserving the learned
per-parent mutation policies **and** the shared global policy. The bundled
`data/round15_selected_population_final.json` starts with best side
`4.006477636998101`. A simple 4-by-3 grid has `L = 4`; the evolutionary
record does not beat that baseline, and no global-optimality claim is made.

## اجرای سریع روی ویندوز / Windows quick start

پیش‌نیاز: **Python 3.11 یا 3.12** (نسخه‌های جدیدتر سازگار نیز معمولاً کار می‌کنند)،
`git` و دسترسی به اینترنت برای نصب بسته‌ها. دستورات زیر را در **PowerShell** یا
**Command Prompt** وارد کنید:

```powershell
git clone https://github.com/amin076/Gerit.git
cd Gerit
py -3 -m pip install -r requirements.txt
py -3 scripts/run_continuation.py --generations 100 --seed 2607 --output-dir results/round16
```

`venv` اجباری نیست. با این حال برای اینکه نسخهٔ بسته‌ها با برنامه‌های Python
دیگر تداخل پیدا نکند، محیط مجازی پیشنهاد می‌شود. اگر از قبل Pillow نصب
کرده‌اید باز هم `pip install -r requirements.txt` را اجرا کنید؛ **Matplotlib**
برای نمودار و **Shapely** برای ممیزی مستقل هندسه لازم‌اند. وابستگی‌های غیرمستقیم
مانند NumPy را خود `pip` نصب می‌کند.

اگر دستور `py` روی سیستم شما شناسایی نشد، به‌جای `py -3` از `python` استفاده
کنید. برای بررسی نصب:

```powershell
py -3 -c "import PIL, matplotlib, shapely; print('Dependencies OK')"
py -3 -m unittest discover -s tests -v
```

### اول یک اجرای کوتاه آزمایشی انجام دهید

```powershell
py -3 scripts/run_continuation.py --generations 1 --seed 2607 --output-dir results/test1
```

بعد از موفقیت تست کوتاه، دستور ۱۰۰نسلی بالا را اجرا کنید. اجرای آزمایش
در همان ترمینال گزارش نسل‌ها و رکوردهای جدید را نشان می‌دهد؛ مدت اجرا با
مشخصات CPU و وضعیت سیستم متغیر است.

### خروجی‌ها کجا ذخیره می‌شوند؟

هر اجرا پوشهٔ جداگانه‌ای می‌سازد؛ برای مثال `results/round16/` شامل موارد زیر است:

| File / directory | Description |
| --- | --- |
| `generation_images/gen_000.png` ... `gen_100.png` | 101 actual population snapshots, each with 20 packings |
| `generation_images.zip` | Downloadable ZIP containing all generation images |
| `complete.zip` | Full auditable run output (images, logs, snapshots and source copies) |
| `best.png`, `progress.png`, `start.png`, `middle.png`, `final.png` | Overview graphics |
| `selected_population_final.json` | **All 20 surviving parents plus each learned policy and global policy** |
| `run_summary.json`, `best_result.json`, `verification.json` | Metrics, best result, validation status |
| `individuals.jsonl`, `selection.jsonl`, `generations.jsonl`, `generations.csv` | Proposals, ancestry, selections, progress and costs |
| `config.json`, `input_selected_population.json`, `source_code/` | Reproducibility information |

**Do not delete `selected_population_final.json`**: that is the exact population
and learned memory needed for the next experiment.

### ادامه از آخرین نسل / Continue from the last saved population

```powershell
py -3 scripts/run_continuation.py --input results/round16/selected_population_final.json --generations 100 --seed 2608 --output-dir results/round17
```

Repeat with the new output file, a new seed and a new output directory.
An existing output folder triggers an error rather than being overwritten.
The `--input` argument accepts any compatible 20-member
`selected_population_final.json` file **with individual `policy` fields and
`global_policy`**. The initial parents are imported unchanged. Each produces
5 proposals per generation (100 candidate proposals/generation). Selection
retains 18 by packing quality and 2 by structural diversity.

### Optional: isolated Python installation

An environment is recommended but **not mandatory**. On Windows:

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe scripts/run_continuation.py --generations 100 --output-dir results/round16-venv
```

On macOS/Linux, use `python3 -m pip install -r requirements.txt`, then
`python3 scripts/run_continuation.py --generations 100 --output-dir results/round16`.

## Algorithm and reproducibility

- Rigid squares are validated using separating-axis checks. Saved images
  represent accepted packing **states**, not collision-free physical
  trajectories between them.
- `gerit/learning.py` samples from ten directional mutation families with
  continuous angle/translation steps. Each parent has a policy genome;
  offspring inherit it. Population-level probabilities are also updated.
- `gerit/reward_v2.py` distinguishes improvement caused directly by mutation,
  additional improvement caused by local compression, and measured counts of
  geometric validation calls.
- Every valid raw child is locally compressed with
  `gerit/local_compression.py`, then selected using 90% fitness / 10% diversity.
- Each run uses a declared RNG seed, append-only JSONL lineage and selected
  population snapshots. Final survivors are checked with Shapely in addition
  to the primary geometric validator.
- `--generations 100` means 100 **new** evolutionary generations; generation 0
  is the imported population, so 101 images are expected.
- The standard `python -m gerit --config configs/five-squares.json` CLI is the
  **earlier baseline motor**. `python -m gerit --learning` uses the original
  learning credit rule, **not** the cost-aware v2 continuation. For current
  12-square experiments use `scripts/run_continuation.py`.

## Python entry points and layout

```text
Gerit/
  README.md
  requirements.txt
  data/round15_selected_population_final.json
  gerit/
    geometry.py
    selection.py
    learning.py
    reward_v2.py
    local_compression.py
    visualization.py
  scripts/run_continuation.py
  tests/test_continuation_cli.py
  results/                  # created locally; do not commit run outputs
```

Older research experiments and regression tests remain in the repository.
The project is experimental numerical optimization, not an independently
certified proof of optimality. Independent floating-point geometry validation
is useful but not formal exact-arithmetic certification.


## Adaptive v4 — progress-window escape (recommended after Round 20)

To continue your own Windows results, **pull the latest repository** and run:

```powershell
cd C:\Physics\Gerit
git pull --ff-only
py -3 -m unittest discover -s tests -v
py -3 scripts/run_adaptive_v4.py --input results/round20-adaptive/selected_population_final.json --generations 300 --seed 2611 --output-dir results/round21-adaptive-v4
```

The v3 runner (`scripts/run_adaptive.py`) is still available and unchanged. Version 4 retains its relative-credit learning and best-packing archive, but measures actual improvement in the last **80 generations**: progress below **0.0001** triggers micro-precision; 20 successive weak-window observations enable structural escape; 60 enable diversification. Legacy 40/80/120 no-record thresholds remain a fallback. Improvement of only a few millionths no longer necessarily restarts the escape schedule.

If the imported population lives beside the prior `generations.jsonl`, v4 reconstructs the rolling history automatically. A v4 continuation stores its own progress state in the final population JSON. No grid packing is injected.

Outputs: `mode_metrics.json` separates births, valid children, direct/final gains, geometric checks and global-record events **by active search mode**. `generations.csv` includes rolling gain and weak-progress streak; archives and per-generation images remain available. See [Adaptive v4 details](docs/ADAPTIVE_V4.md). No additional dependencies.


## Grid-aware search for any square count (optional after Round 21)

**Why did earlier code show 5×5 for 12 squares?** In v3/v4, `SIDE_CAP=5.0` was a search acceptance cap *and* a fixed image scale—not the initial parent's bounding side. Twenty genuine saved parents from the prior round were imported instead.

A valid axis-aligned grid of **n** unit squares has side `ceil(sqrt(n))`; this is a **constructive upper bound** on the optimal side, **not** a lower bound. Basic area provides the lower bound `sqrt(n)`. Examples: 12 squares fit in 4×3 within L=4; 23 squares in L=5; 26 squares in L=6.

To continue the **real evolved population** from your latest local Round 21, without injecting a known grid:

```powershell
cd C:\Physics\Gerit
git pull --ff-only
py -3 -m unittest discover -s tests -p "test_grid_bounds.py" -v
py -3 scripts/run_adaptive_auto.py --input results/round21-adaptive-v4/selected_population_final.json --generations 300 --seed 2612 --output-dir results/round22-grid-aware
```

The new runner inherits all learned parent/global policies and rolling stagnation history. Its default `--side-cap auto` uses a focused cap `max(ceil(sqrt(n)), imported best side)+0.15`, but allows each *diverse parent* to mutate up to `max(focused cap, its own side+0.15)`. Thus it never invalidates the inherited 4.00... parents or gratuitously eliminates worse exploratory lineages. Alter the exploratory allowance with `--cap-margin 0.25`; pass `--side-cap 5` for the legacy fixed cap. Population tiles show the **actual individual side**, not a fixed 5×5 frame.

To *explicitly* start an **independent known-grid control** (not a discovered evolutionary record):

```powershell
py -3 scripts/make_grid_population.py --squares 23 --output data/grid23.json
py -3 scripts/run_adaptive_auto.py --input data/grid23.json --generations 100 --seed 2323 --output-dir results/grid23-explicit
```

The grid initializer creates 20 labelled copies of the known valid grid, with neutral policy memory; other values such as `--squares 26` work too. **Do not** attribute the known grid's initial L to the evolutionary search. The previous `run_adaptive_v4.py` remains unchanged for reproducibility. See [design and limits](docs/GRID_AWARE_SEARCH.md).


## Connected all-parallel tiling seeds — structured diversity

A new **optional seed source** constructs edge-connected, axis-aligned groups of unit squares from positive row-width compositions. It works for arbitrary positive n, without fixing the row profiles to 12. For 12, feasible side-4 shapes include `4+4+4`, `4+4+3+1`, `4+4+2+2` and `4+3+3+2`. For 23, the grid-side bound is 5; for 26, it is 6. The shape bank can optionally allow wider connected variants using `--tiling-extra-side 1`.

To **continue Round 21** from the actual inherited population, while adding **three constructive diversity seeds** and protecting the original unseeded evolutionary lineage:

```powershell
cd C:\Physics\Gerit
git pull --ff-only
py -3 -m unittest discover -s tests -p "test_connected_tilings.py" -v
py -3 scripts/run_adaptive_tilings.py --input results/round21-adaptive-v4/selected_population_final.json --generations 300 --seed 2613 --output-dir results/round22-connected --tiling-seeds 3
```

Initial population: **17 inherited parents + 3 known constructive tilings**. Best original parent and global learned policy are retained; the best independent nonconstructive lineage remains archived and represented in breeding. `--tiling-seeds 0` disables injection. The generated layouts have all angles 0, unit-edge adjacency and rigorous valid geometry; subsequent evolutionary changes may rotate/move them. The v4 reward and rolling-window escape remain in use.

**Important:** injecting known tilings for n=12 immediately makes the *overall* best side `L=4` at generation 0. **That is not an evolutionary discovery.** `run_summary.json` separately reports `evolved_baseline_before_seed_injection`, `best_unseeded_evolutionary_lineage`, `best_record_origin` and `constructive_initial_seed_count`, while per-person `constructive_ancestor` labels propagate across runs. The original imported population and the actual 20 starting genomes are both archived. With a seeded final population, use `--tiling-seeds 0` in the next run to avoid reinjecting known answers.

For a **new study**, construct a diverse 23-square input, or substitute 26:

```powershell
py -3 scripts/make_tiling_population.py --squares 23 --output data/connected23.json
py -3 scripts/run_adaptive_tilings.py --input data/connected23.json --tiling-seeds 0 --generations 100 --seed 2323 --output-dir results/connected23
```

Read [full details and scientific attribution notes](docs/CONNECTED_TILINGS.md). Prior auto/v4 runners remain unchanged and usable for fair unseeded controls; no new dependencies.

### Fix for connected tilings and inherited v4 stagnation history

The **2026-10-27 hotfix** resets only the rolling stagnation timer if newly injected constructed layouts provide a better initial best (such as 12-square L=4 replacing an imported best near 4.005). Before this fix, a saved progress window could trigger `ValueError: Saved rolling best does not match imported best`. Learning weights and original provenance stay intact. With `--tiling-seeds 0`, the previous window is still inherited.

If a prior attempt created `results/round22-connected` and failed before generation 1, do **not** reuse that existing directory. Continue safely with:

```powershell
git pull --ff-only
py -3 scripts/run_adaptive_tilings.py --input results/round21-adaptive-v4/selected_population_final.json --generations 300 --seed 2613 --output-dir results/round22-connected-fixed --tiling-seeds 3
```

## Fresh independent 12-square experiment — 25 parents, 300 generations

This is the **recommended new experiment** when you want to start from zero, without inheriting any old population, previous fitness records or learned policy weights. It explicitly uses *both* connected axis-aligned square constructions and newly randomized/rotated placements. **All initializers compete in one population**; the selected parents do not have permanent source quotas.

On Windows:

```powershell
cd C:\Physics\Gerit
git pull --ff-only
py -3 -m unittest discover -s tests -p "test_fresh_25.py" -v
py -3 scripts/run_fresh_25.py --squares 12 --population 25 --structural-seeds 7 --generations 300 --seed 2715 --output-dir results/fresh12-p25-g300
```

- Starting population: **7 distinct constructive connected tilings + 18 new stochastic/rotated or sparse packings** = 25 parents, all strictly valid.
- All policy weights begin neutral. The runner has **no `--input`** option, does not read `results/` from prior sessions, and does not import learned global weights.
- **5 births per parent** × 25 parents = **125 attempted offspring per generation**, 37,500 proposals over 300 generations; 301 population images, full logs, independent Shapely validation and audited ZIPs.
- Selection has **25 survivors** every generation: quality + diversity close to the record + a few wider explorers. All source labels are ignored by selection. Keeps the current adaptive relative learning, local compression, micro-search and stagnation-triggered structural relocation.
- L=4 for n=12 is available immediately as a mathematically constructed starting arrangement; evolutionary progress is a **strict result below the initial best**, not generation-zero grid inclusion.
- **Do not delete old runs** to reset this experiment. They are never read. If you choose to clean old local files, back up your data separately; the program never deletes existing results automatically.

Full protocol and output details: [Fresh start guide](docs/FRESH_START_25.md).

### Follow-up after auditing the completed 300-generation archive (2026-10-27)

The first independent seed-2715 run (`results/fresh12-p25-g300`) completed with **L=4**, 20,971 valid children out of 37,500, and no global improvement. Reconstructed ancestry showed **22 of 25 final parents** came from the initial seven connected tilings; the 18 stochastic starters were mostly far above the grid bound and disappeared immediately.

**Fresh initialization v2:** the generator now starts most randomized geometries close to grid L using *multiple different connected silhouettes*, not just the canonical grid, with 9 rigidly tilted, 6 individually perturbed, and 3 broad sparse candidates for n=12, 25 parents, 7 structural seeds. Geometry and source-independent selection remain unchanged. A preflight with seed 2715 retained six stochastic lineages after generation one (versus three before); long-run performance has **not** yet been established.

Every run now logs initial source breakdown and selected ancestry counts; selection **still ignores** source labels. The prior complete ZIP and its embedded code remain the scientific record of the old version. New runs must use a **new output directory**:

```powershell
git pull --ff-only
py -3 -m unittest discover -s tests -p "test_fresh_25.py" -v
py -3 scripts/run_fresh_25.py --squares 12 --population 25 --structural-seeds 7 --generations 300 --seed 2715 --output-dir results/fresh12-p25-g300-initv2
```

Detailed ancestry audit: [Fresh start guide](docs/FRESH_START_25.md). Compare multiple matched seeds and geometric-check budgets before crediting gains to the modified initializer.

