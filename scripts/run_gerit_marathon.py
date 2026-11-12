"""Time-boxed, breadth-first automatic Gerit experiment marathon.

Runs across N=2..1000 in balanced hundred-N bands, alternating structural
N-1 -> N growth with fixed-N deep search. Every subprocess has a hard
per-task deadline and its own logs/checkpoints. The registry is updated
only through independently certified, strictly better candidates. With
--apply, validated results are offered to the existing registry. Resume
safely recovers interrupted candidates. The original evolutionary solver
and historical jumps are untouched.

Example:
  py -3 scripts/run_gerit_marathon.py --hours 5.5 --apply
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gerit.packing_io import load_packing_json
from scripts.kaggle_best_registry import read_registry, propose_improvement
from scripts.run_deep_elastic import _certify, _packing_from_record, _write_json


def _now():
    return datetime.now(timezone.utc).isoformat()


def _best_available(bank, state, n):
    """Prefer a known certified, locally saved improvement over the bank."""
    side = float(bank["problems"][str(n)]["side"])
    file = state["best_files"].get(str(n))
    if file:
        record = load_packing_json(file)
        if int(record["n"]) != n:
            raise ValueError(f"Wrong N in saved marathon candidate: {file}")
        p = _packing_from_record(record)
        valid, reason = _certify(p)
        if not valid:
            raise ValueError(f"Uncertified marathon candidate {file}: {reason}")
        if p.container_side < side - 1e-10:
            return p.container_side, file
    return side, None


def _candidates(bank, state, config):
    """Return growth and deep tasks ordered by breadth then score opportunity."""
    lo, hi = config["min_n"], config["max_n"]
    attempted = {(int(j["n"]), j["method"]) for j in state["jobs"]}
    band_counts = {}
    for j in state["jobs"]:
        band = (int(j["n"]) - 1) // 100
        band_counts[band] = band_counts.get(band, 0) + 1
    growth, deep = [], []
    for n in range(max(2, lo), hi + 1):
        side, _ = _best_available(bank, state, n)
        potential = (side - math.sqrt(n)) / math.sqrt(n)
        if potential <= 1e-5:
            continue
        band = (n - 1) // 100
        seen = band_counts.get(band, 0)
        if (n, "growth") not in attempted:
            founder_side, founder_file = _best_available(bank, state, n - 1)
            advantage = side - founder_side
            if advantage > 0.002:
                # Grid-to-next-grid transitions get substantial priority.
                opportunity = (side - max(math.sqrt(n), founder_side)) / math.sqrt(n)
                growth.append((seen, -opportunity, n, "growth", founder_file))
        if (n, "deep") not in attempted and potential > 0.002:
            deep.append((seen, -potential, n, "deep", None))
    growth.sort()
    deep.sort()
    return growth, deep


def _choose(bank, state, config):
    growth, deep = _candidates(bank, state, config)
    # Schedule fixed-N exploration every fourth task; otherwise favor
    # proven N-1 growth. Do not get trapped at a single difficult N.
    prefer_deep = len(state["jobs"]) % 4 == 3
    options = (deep, growth) if prefer_deep else (growth, deep)
    for group in options:
        if group:
            _, _, n, method, founder_file = group[0]
            return n, method, founder_file
    return None


def _worker(argv, logfile, deadline):
    """Stream subprocess logs to CMD and enforce a monotonic wall-clock cap.

    No shell is used. The Python child is killed on deadline; previously
    checkpointed best_valid.json/best_growth.json remains available.
    """
    import subprocess

    logfile = Path(logfile)
    logfile.parent.mkdir(parents=True, exist_ok=True)
    print("COMMAND " + subprocess.list2cmdline(argv), flush=True)
    timed_out = False
    with logfile.open("w+", encoding="utf-8", errors="replace") as stream:
        child = subprocess.Popen(
            argv, cwd=str(ROOT), stdout=stream, stderr=subprocess.STDOUT)
        position = 0
        try:
            while child.poll() is None:
                time.sleep(1.0)
                stream.flush()
                with logfile.open(encoding="utf-8", errors="replace") as reader:
                    reader.seek(position)
                    new = reader.read()
                    position = reader.tell()
                if new:
                    print(new, end="" if new.endswith("\n") else "\n", flush=True)
                if time.monotonic() >= deadline:
                    timed_out = True
                    child.kill()
                    child.wait()
                    break
        except KeyboardInterrupt:
            child.kill()
            child.wait()
            raise
        stream.flush()
        with logfile.open(encoding="utf-8", errors="replace") as reader:
            reader.seek(position)
            last = reader.read()
        if last:
            print(last, end="" if last.endswith("\n") else "\n", flush=True)
    return {"returncode":child.returncode, "timed_out":timed_out}


def _validate_file(path, n):
    if not Path(path).is_file():
        return None
    record = load_packing_json(path)
    if int(record["n"]) != n:
        raise ValueError(f"Candidate N mismatch: {path}")
    packing = _packing_from_record(record)
    valid, reason = _certify(packing)
    if not valid:
        raise ValueError(f"Candidate certification failed: {reason}")
    return record


def _take_candidate(bank_file, state, path, n, job_id, apply):
    candidate = _validate_file(path, n)
    if candidate is None:
        return None
    bank = read_registry(bank_file)
    previous, _ = _best_available(bank, state, n)
    side = float(candidate["side"])
    accepted = False
    if side < previous - 1e-10:
        # Strict + independent interval SAT is repeated before applying.
        if apply:
            result = propose_improvement(
                bank_file, candidate, source="gerit-marathon",
                experiment_id=job_id, generation=0,
                operator="marathon_structural_or_deep")
            accepted = bool(result["accepted"])
        state["best_files"][str(n)] = str(path)
        print(f"MARATHON_IMPROVED N={n} old={previous:.12f} "
              f"new={side:.12f} registered={accepted}", flush=True)
    return {"side":side, "registered":accepted,
            "improved":side < previous - 1e-10}


def _recover_active(bank_file, state, apply):
    active = state.pop("active", None)
    if not active:
        return
    n = int(active["n"])
    base = Path(active["folder"])
    recovered = []
    for file in (base / "growth" / "best_growth.json",
                 base / "deep" / "best_valid.json"):
        if file.is_file():
            try:
                recovered.append(_take_candidate(
                    bank_file, state, file, n, active["id"], apply))
            except (ValueError, KeyError, OSError) as exc:
                print(f"RECOVERY_REJECTED {file}: {exc}", flush=True)
    active.update(status="interrupted-recovered", recovered=recovered,
                  finished_at=_now())
    state["jobs"].append(active)


def _score(bank, state):
    return math.fsum(
        (min(float(bank["problems"][str(n)]["side"]),
             _best_available(bank, state, n)[0]) / math.sqrt(n) - 1.0)
        for n in range(1, 1001))


def _summary(bank_file, state):
    bank = read_registry(bank_file)
    originals = state["initial_sides"]
    improved = [n for n in range(1, 1001)
                if _best_available(bank, state, n)[0]
                < float(originals[str(n)]) - 1e-10]
    return {
        "updated_at": _now(),
        "tasks_completed": len(state["jobs"]),
        "growth_tasks": sum(j["method"] == "growth" for j in state["jobs"]),
        "deep_tasks": sum(j["method"] == "deep" for j in state["jobs"]),
        "tasks_with_candidates": sum(bool(j.get("best_file")) for j in state["jobs"]),
        "improved_problems": len(improved),
        "improved_n": improved,
        "initial_score": state["initial_score"],
        "projected_score": _score(bank, state),
        "bank_score": float(bank["total_score"]),
        "total_score_gain": state["initial_score"] - _score(bank, state),
    }


def _save_state(folder, bank_file, state):
    _write_json(folder / "marathon_state.json", state)
    _write_json(folder / "summary.json", _summary(bank_file, state))


def run(*, registry, output_dir, hours=5.5, max_task_minutes=12.0,
        min_n=2, max_n=1000, growth_attempts=8, growth_iterations=130,
        deep_generations=50, deep_iterations=90,
        seed=20261122, apply=False, resume=False, max_tasks=1000):
    if not (hours > 0 and max_task_minutes > 0 and 2 <= min_n <= max_n <= 1000
            and growth_attempts > 0 and growth_iterations > 0
            and deep_generations > 0 and deep_iterations > 0
            and max_tasks > 0):
        raise ValueError("Invalid marathon parameters")
    bank_file = Path(registry).resolve()
    folder = Path(output_dir).resolve()
    config = dict(min_n=min_n, max_n=max_n,
                  growth_attempts=growth_attempts,
                  growth_iterations=growth_iterations,
                  deep_generations=deep_generations,
                  deep_iterations=deep_iterations, seed=seed,
                  apply=apply, registry=str(bank_file))
    if resume:
        state = json.loads((folder / "marathon_state.json").read_text(encoding="utf-8"))
        if state["config"] != config:
            raise ValueError("Resume configuration differs; retain the original flags")
        _recover_active(bank_file, state, apply)
    else:
        if folder.exists():
            raise FileExistsError(f"Preserving prior marathon: {folder}")
        bank = read_registry(bank_file)
        folder.mkdir(parents=True)
        state = {
            "created_at": _now(), "config": config,
            "initial_sides": {str(n): float(bank["problems"][str(n)]["side"])
                              for n in range(1, 1001)},
            "initial_score": float(bank["total_score"]),
            "best_files": {}, "jobs": [],
        }
    if apply and not resume:
        import shutil
        shutil.copy2(bank_file, folder / "registry_before_marathon.json")
        print(f"REGISTRY_BACKUP {folder / 'registry_before_marathon.json'}", flush=True)
    _save_state(folder, bank_file, state)
    start = time.monotonic()
    end = start + hours * 3600
    print(f"MARATHON_STARTED hours={hours} range={min_n}..{max_n} "
          f"max_task_minutes={max_task_minutes} apply={apply} "
          f"resume={resume} score={_summary(bank_file,state)['projected_score']:.12f}",
          flush=True)
    try:
        while time.monotonic() < end - 20 and len(state["jobs"]) < max_tasks:
            bank = read_registry(bank_file)
            chosen = _choose(bank, state, config)
            if chosen is None:
                print("MARATHON_NO_MORE_TARGETS", flush=True)
                break
            n, method, source_file = chosen
            number = len(state["jobs"]) + 1
            job_id = f"marathon-{seed}-{number:04d}-n{n:04d}-{method}"
            job_folder = folder / f"job_{number:04d}_n{n:04d}_{method}"
            if job_folder.exists():
                raise FileExistsError(f"Cannot overwrite: {job_folder}")
            job_folder.mkdir(parents=True)
            active = {"id": job_id, "n": n, "method": method,
                      "folder": str(job_folder), "started_at": _now(),
                      "founder_file": source_file}
            state["active"] = active
            _save_state(folder, bank_file, state)
            task_deadline = min(end, time.monotonic() + max_task_minutes * 60)
            attempts = int(config["growth_attempts"])
            iterations = int(config["growth_iterations"])
            job_result = {"status": "finished", "best_file": None,
                          "stages": []}
            try:
                deep_seed = None
                if method == "growth":
                    growth_deadline = min(
                        task_deadline, time.monotonic()
                        + max(30., max_task_minutes * 60 * .67))
                    cmd = [sys.executable, "-u",
                           str(ROOT / "scripts" / "run_structural_growth.py"),
                           "--registry", str(bank_file), "--n", str(n),
                           "--attempts", str(attempts),
                           "--iterations", str(iterations),
                           "--deep-generations", "0",
                           "--seed", str(seed + n + number * 1009),
                           "--output-dir", str(job_folder / "growth")]
                    if source_file:
                        cmd.extend(["--source-file", source_file])
                    job_result["stages"].append(
                        {"name": "growth", **_worker(
                            cmd, job_folder / "growth.log", growth_deadline)})
                    candidate_file = job_folder / "growth" / "best_growth.json"
                    result = _take_candidate(bank_file, state, candidate_file,
                                             n, job_id, apply)
                    if result is not None:
                        deep_seed = candidate_file
                        job_result["best_file"] = str(candidate_file)
                if method == "deep" or deep_seed is not None:
                    if time.monotonic() < task_deadline - 10:
                        cmd = [sys.executable, "-u",
                               str(ROOT / "scripts" / "run_deep_elastic.py"),
                               "--registry", str(bank_file), "--n", str(n),
                               "--generations", str(deep_generations),
                               "--iterations", str(deep_iterations),
                               "--log-every", "10",
                               "--seed", str(seed + n + number * 2003),
                               "--output-dir", str(job_folder / "deep")]
                        if deep_seed:
                            cmd.extend(["--candidate-file", str(deep_seed)])
                        job_result["stages"].append(
                            {"name": "deep", **_worker(
                                cmd, job_folder / "deep.log", task_deadline)})
                        candidate_file = job_folder / "deep" / "best_valid.json"
                        result = _take_candidate(bank_file, state, candidate_file,
                                                 n, job_id, apply)
                        if result is not None:
                            job_result["best_file"] = str(candidate_file)
                if any(x["timed_out"] for x in job_result["stages"]):
                    job_result["status"] = "time-limited"
                elif any(x["returncode"] != 0 for x in job_result["stages"]):
                    job_result["status"] = "worker-error"
            except Exception as exc:
                job_result["status"] = "error"
                job_result["error"] = f"{type(exc).__name__}: {exc}"
                print(f"MARATHON_JOB_ERROR N={n} {exc}", flush=True)
            active.update(job_result, finished_at=_now())
            state["jobs"].append(active)
            state.pop("active", None)
            _save_state(folder, bank_file, state)
            summary = _summary(bank_file, state)
            print(f"MARATHON_TASK {number} N={n} method={method} "
                  f"status={active['status']} improved={summary['improved_problems']} "
                  f"score={summary['projected_score']:.12f} "
                  f"remaining_minutes={(end - time.monotonic())/60:.1f}",
                  flush=True)
    except KeyboardInterrupt:
        print("MARATHON_INTERRUPTED: checkpoints preserved; use --resume",
              flush=True)
    finally:
        _save_state(folder, bank_file, state)
        summary = _summary(bank_file, state)
        print(f"MARATHON_FINISHED tasks={summary['tasks_completed']} "
              f"improved={summary['improved_problems']} "
              f"score={summary['projected_score']:.12f} "
              f"summary={folder / 'summary.json'}", flush=True)
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--registry",
                   default="results/kaggle_baseline/best_registry.json")
    p.add_argument("--output-dir",
                   default="results/kaggle_auto/marathon_20261112")
    p.add_argument("--hours", type=float, default=5.5)
    p.add_argument("--max-task-minutes", type=float, default=12.)
    p.add_argument("--min-n", type=int, default=2)
    p.add_argument("--max-n", type=int, default=1000)
    p.add_argument("--growth-attempts", type=int, default=8)
    p.add_argument("--growth-iterations", type=int, default=130)
    p.add_argument("--deep-generations", type=int, default=50)
    p.add_argument("--deep-iterations", type=int, default=90)
    p.add_argument("--seed", type=int, default=20261122)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--max-tasks", type=int, default=1000)
    p.add_argument("--plan-only", action="store_true",
                   help="Print the first 20 initial target choices; do no work")
    a = p.parse_args()
    if a.plan_only:
        bank = read_registry(a.registry)
        state = {"jobs": [], "best_files": {}}
        config = {"min_n": a.min_n, "max_n": a.max_n}
        print("MARATHON_PLAN (initial registry; later choices adapt to results)")
        for i in range(20):
            choice = _choose(bank, state, config)
            if choice is None:
                break
            n, method, source_file = choice
            print(f"{i+1:02d}. N={n} method={method}"
                  f" source_N={n-1 if method == 'growth' else n}")
            state["jobs"].append({"n": n, "method": method})
        return
    run(registry=a.registry, output_dir=a.output_dir, hours=a.hours,
        max_task_minutes=a.max_task_minutes, min_n=a.min_n,
        max_n=a.max_n, growth_attempts=a.growth_attempts,
        growth_iterations=a.growth_iterations,
        deep_generations=a.deep_generations,
        deep_iterations=a.deep_iterations, seed=a.seed,
        apply=a.apply, resume=a.resume, max_tasks=a.max_tasks)


if __name__ == "__main__":
    main()
