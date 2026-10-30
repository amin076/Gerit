@echo off
setlocal EnableExtensions
pushd "%~dp0"
if errorlevel 1 exit /b 1
echo Running five INDEPENDENT fresh-start 18-square experiments
echo Fixed initial geometry: 8x8 grid; no --initial-state or warm start
for %%S in (4536 4537 4538 4539 4540) do (
  echo.
  echo ==================== Seed %%S ====================
  py -3 -u -m examples.square_packing ^
    --square-count 18 ^
    --iterations 3000 ^
    --initial-side 8 ^
    --initial-mode grid ^
    --initial-angle-mode zero ^
    --initial-parents 1 ^
    --max-parents 4 ^
    --max-forward-branches 2 ^
    --max-historical-branches 2 ^
    --adaptive-historical ^
    --fair-historical-budget ^
    --historical-forward-reserve 2 ^
    --historical-lookback-min 100 ^
    --historical-lookback-max 1500 ^
    --historical-trial-generations 300 ^
    --historical-depth-budget-ratio 0.75 ^
    --historical-max-trial-generations 1200 ^
    --historical-progress-extension 100 ^
    --historical-progress-window 100 ^
    --historical-min-progress-fraction 0.00001 ^
    --historical-spawn-interval 100 ^
    --historical-archive-interval 20 ^
    --historical-stall-windows 2 ^
    --children-per-parent 10 ^
    --population-adjust-interval 20 ^
    --reservoir-size 128 ^
    --evaluation-budget 350000 ^
    --compression-attempts 4 ^
    --rotation-attempts 12 ^
    --operator-set legacy-hybrid ^
    --log-every 10 ^
    --checkpoint-every 10 ^
    --lineage-video ^
    --fps 30 ^
    --image-width 900 ^
    --seed %%S ^
    --output-dir results\squares-18-fresh8-p4-g3000-%%S
  if errorlevel 1 (
    echo FAILED seed %%S. Stopping to protect incomplete results.
    popd
    exit /b 1
  )
)
py -3 -m examples.summarize_multiseed --results-root results --include-seed 4535
if errorlevel 1 (
  echo Report generation failed; original runs remain intact.
  popd
  exit /b 1
)
popd
echo All independent runs completed.
endlocal
