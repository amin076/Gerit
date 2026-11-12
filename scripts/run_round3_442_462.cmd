@echo off
setlocal
cd /d "%~dp0.."
if errorlevel 1 exit /b 1

echo === GERIT ROUND 2: independently audit certified improvements ===
py -3 scripts/promote_auto_sweep.py --sweep-dir results/kaggle_auto/round2_n401_420 --report results/kaggle_auto/round2_n401_420_audit.json
if errorlevel 1 (
  echo ERROR: Audit failed. Registry was NOT changed by this launcher.
  exit /b 1
)

echo === GERIT ROUND 2: register certified winners in 1000-case bank ===
py -3 scripts/promote_auto_sweep.py --sweep-dir results/kaggle_auto/round2_n401_420 --apply --report results/kaggle_auto/round2_n401_420_applied.json
if errorlevel 1 (
  echo ERROR: Promotion failed. Inspect the audit and registry status.
  exit /b 1
)
py -3 scripts/kaggle_best_registry.py status
if errorlevel 1 exit /b 1

echo === GERIT ROUND 3: 21^2 to 22^2, first half N442..462 ===
echo 30 growth attempts, 500 repair iterations, 200 deep generations,
echo 200 deep iterations; new results remain a dry-run.
py -3 scripts/run_auto_family_sweep.py --first 442 --max-n 462 --attempts 30 --iterations 500 --deep-generations 200 --deep-iterations 200 --seed 20261114 --output-dir results/kaggle_auto/round3_n442_462
if errorlevel 1 (
  echo ERROR: Campaign interrupted or destination exists.
  echo For a previously started campaign, run its command with --resume.
  exit /b 1
)
echo === ROUND 3 FINISHED ===
endlocal
