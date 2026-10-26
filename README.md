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