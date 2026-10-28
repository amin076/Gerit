"""Gerit generic search engine: no assumptions about a particular problem domain."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from copy import deepcopy
from pathlib import Path
import json
import math
import random


@dataclass
class Settings:
    iterations: int = 10000
    children_per_parent: int = 10
    max_parents: int = 5
    stagnation_window: int = 200
    significant_gain: float = 1e-6
    competition_generations: int = 200
    evaluation_budget: int = 300000
    reservoir_size: int = 128
    branch_seed_attempts: int = 256
    min_distance: float = 1e-6
    absolute_regression: float = 0.15
    learning_rate: float = 0.15
    exploration_floor: float = 0.05
    maximize: bool = False
    seed: int = 2716
    checkpoint_every: int = 200
    output_dir: str = "results/gerit-core"

    def validate(self, operators):
        for key in ("iterations", "children_per_parent", "max_parents", "stagnation_window",
                    "competition_generations", "evaluation_budget", "reservoir_size",
                    "branch_seed_attempts", "checkpoint_every"):
            if getattr(self, key) < 1:
                raise ValueError(f"{key} must be positive")
        if not operators:
            raise ValueError("At least one operator required")
        if not 0 <= self.exploration_floor <= 1 or not 0 < self.learning_rate <= 1:
            raise ValueError("Invalid learning parameters")
        for key in ("significant_gain", "min_distance", "absolute_regression"):
            value = getattr(self, key)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"Invalid {key}")


@dataclass
class Candidate:
    state: object
    score: float


@dataclass
class Result:
    best_state: object
    best_objective: float
    evaluations: int
    generations: int
    history: list
    events: list


class Search:
    """Problem: initial(rng), evaluate(state), feasible(state), distance(a,b), encode(state).
    Operators: mapping from name to function(state,rng,intensity)->new_state.
    Internal scores are minimized; maximize=True negates the supplied objective.
    """

    def __init__(self, problem, operators, settings=None):
        self.cfg = settings or Settings()
        self.cfg.validate(operators)
        self.problem = problem
        self.operators = dict(operators)
        self.rng = random.Random(self.cfg.seed)
        self.weights = {name: 1.0 for name in operators}
        self.evaluations = 0
        self.generation = 0
        self.best = None
        self.pool = []
        self.parents = []
        self.events = []
        self.history = []
        self.checkpoint_step = 0
        self.checkpoint_score = float("inf")
        self.competition_end = None
        self.output = Path(self.cfg.output_dir)
        self.output.mkdir(parents=True, exist_ok=True)

    def _atomic(self, filename, payload):
        path = self.output / filename
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf8")
        tmp.replace(path)

    def _objective(self, score):
        return -score if self.cfg.maximize else score

    def _save_best(self):
        if self.best is not None:
            self._atomic("best.json", {
                "generation": self.generation, "evaluations": self.evaluations,
                "objective": self._objective(self.best.score),
                "state": self.problem.encode(self.best.state)
            })

    def _eval(self, state):
        if self.evaluations >= self.cfg.evaluation_budget:
            return None
        self.evaluations += 1
        if not self.problem.feasible(state):
            return None
        value = float(self.problem.evaluate(state))
        if not math.isfinite(value):
            return None
        candidate = Candidate(deepcopy(state), -value if self.cfg.maximize else value)
        if self.best is None or candidate.score < self.best.score:
            self.best = deepcopy(candidate)
            self._save_best()
        return candidate

    def _remember(self, candidate):
        cfg = self.cfg
        if candidate.score > self.best.score + cfg.absolute_regression:
            return
        if any(self.problem.distance(candidate.state, x.state) < cfg.min_distance for x in self.pool):
            return
        self.pool.append(deepcopy(candidate))
        if len(self.pool) > cfg.reservoir_size:
            # Preserve the best pool candidate and discard the least diverse other.
            best = min(range(len(self.pool)), key=lambda i: self.pool[i].score)
            candidates = [i for i in range(len(self.pool)) if i != best]
            drop = min(candidates, key=lambda i: min(
                self.problem.distance(self.pool[i].state, self.pool[j].state)
                for j in range(len(self.pool)) if j != i
            ))
            self.pool.pop(drop)

    def _mutate(self, parent, intensity=1.0):
        names = list(self.operators)
        total = sum(self.weights.values())
        floor = self.cfg.exploration_floor
        probs = [(1-floor)*self.weights[n]/total + floor/len(names) for n in names]
        name = self.rng.choices(names, weights=probs, k=1)[0]
        state = self.operators[name](deepcopy(parent.state), self.rng, intensity)
        child = self._eval(state)
        if child is not None:
            self._remember(child)
        reward = 1.0 if child is not None and child.score < parent.score else 0.0
        rate = self.cfg.learning_rate
        self.weights[name] = max(0.02, (1-rate)*self.weights[name] + rate*(0.02+reward))
        return child

    def _spawn(self, incumbent):
        cfg = self.cfg
        selected = [deepcopy(incumbent)]
        def select_from_pool():
            remaining = [c for c in self.pool if c.score <= incumbent.score + cfg.absolute_regression]
            while remaining and len(selected) < cfg.max_parents:
                candidate = max(remaining, key=lambda c: (
                    min(self.problem.distance(c.state, p.state) for p in selected), -c.score
                ))
                remaining.remove(candidate)
                if min(self.problem.distance(candidate.state, p.state) for p in selected) >= cfg.min_distance:
                    selected.append(deepcopy(candidate))
        select_from_pool()
        attempts = 0
        while len(selected) < cfg.max_parents and attempts < cfg.branch_seed_attempts and self.evaluations < cfg.evaluation_budget:
            attempts += 1
            self._mutate(self.rng.choice(selected), 1.0 + 2.0*self.rng.random())
            select_from_pool()
        self.events.append({"generation": self.generation,
                            "event": "branch_start" if len(selected)>1 else "branch_seed_shortfall",
                            "requested": cfg.max_parents, "created": len(selected),
                            "attempts": attempts})
        return selected

    def _status(self):
        self._atomic("status.json", {
            "generation": self.generation, "evaluations": self.evaluations,
            "best_objective": self._objective(self.best.score),
            "parents": len(self.parents), "competition_end": self.competition_end,
            "operator_weights": self.weights,
            "last_event": self.events[-1] if self.events else None,
        })

    def run(self):
        cfg = self.cfg
        initial = self._eval(self.problem.initial(self.rng))
        if initial is None:
            raise ValueError("Initial state must be feasible and have finite objective")
        self.parents = [initial]
        self._remember(initial)
        self.checkpoint_score = self.best.score
        try:
            for step in range(1, cfg.iterations+1):
                if self.evaluations >= cfg.evaluation_budget:
                    self.events.append({"generation": self.generation, "event": "budget_exhausted"})
                    break
                self.generation = step
                next_parents = []
                for parent in self.parents:
                    improved = []
                    for _ in range(cfg.children_per_parent):
                        if self.evaluations >= cfg.evaluation_budget:
                            break
                        child = self._mutate(parent)
                        if child is not None and child.score < parent.score:
                            improved.append(child)
                    next_parents.append(min(improved, key=lambda x:x.score) if improved else parent)
                self.parents = next_parents
                if self.competition_end is not None and step >= self.competition_end:
                    winner_index = min(range(len(self.parents)), key=lambda i:self.parents[i].score)
                    winner = self.parents[winner_index]
                    if self.best.score < winner.score:
                        winner = deepcopy(self.best)
                        winner_index = -1
                    self.parents = [winner]
                    self.competition_end = None
                    self.events.append({"generation":step,"event":"branch_end",
                                        "winner_index":winner_index,
                                        "objective":self._objective(winner.score)})
                if self.competition_end is None and len(self.parents) == 1 and step-self.checkpoint_step >= cfg.stagnation_window:
                    gain = self.checkpoint_score-self.best.score
                    if gain >= cfg.significant_gain:
                        self.checkpoint_step = step
                        self.checkpoint_score = self.best.score
                    elif cfg.max_parents > 1:
                        self.parents = self._spawn(self.parents[0])
                        if len(self.parents) > 1:
                            self.competition_end = step + cfg.competition_generations
                        self.checkpoint_step = step
                        self.checkpoint_score = self.best.score
                self.history.append({"generation":step,"evaluations":self.evaluations,
                                     "best_objective":self._objective(self.best.score),
                                     "parents":len(self.parents)})
                if step % cfg.checkpoint_every == 0:
                    self._status()
        finally:
            self._save_best()
            self._status()
            self._atomic("run_summary.json", {
                "settings":asdict(cfg), "generation":self.generation,
                "evaluations":self.evaluations, "best_objective":self._objective(self.best.score),
                "events":self.events
            })
        return Result(deepcopy(self.best.state), self._objective(self.best.score),
                      self.evaluations, self.generation, self.history, self.events)
