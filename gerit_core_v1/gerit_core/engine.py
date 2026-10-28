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
    competition_generations: int = 200  # lineage trend memory horizon (legacy CLI flag)
    population_adjust_interval: int = 20
    history_depth: int = 120
    progress_smoothing: float = 0.35
    low_progress_ratio: float = 0.25
    high_progress_ratio: float = 0.80
    trend_weight: float = 0.35
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
                    "branch_seed_attempts", "checkpoint_every",
                    "population_adjust_interval", "history_depth"):
            if getattr(self, key) < 1:
                raise ValueError(f"{key} must be positive")
        if not operators:
            raise ValueError("At least one operator required")
        if not 0 <= self.exploration_floor <= 1 or not 0 < self.learning_rate <= 1:
            raise ValueError("Invalid learning parameters")
        if not 0 < self.progress_smoothing <= 1:
            raise ValueError("progress_smoothing must be in (0,1]")
        if not 0 <= self.low_progress_ratio < self.high_progress_ratio:
            raise ValueError("Need 0 <= low_progress_ratio < high_progress_ratio")
        if not 0 <= self.trend_weight <= 1:
            raise ValueError("trend_weight must be in [0,1]")
        for key in ("significant_gain", "min_distance", "absolute_regression"):
            value = getattr(self, key)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"Invalid {key}")


@dataclass
class Candidate:
    state: object
    score: float


@dataclass
class Lineage:
    candidate: Candidate
    born: int
    progress: list  # improvement against its own parent, one value per generation


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
        self.competition_end = None  # deprecated; retained for existing output readers
        self.snapshots = []          # historical parent states, independent of geometry
        self.reference_gain = None   # adaptive local progress scale
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

    def _remember_history(self):
        """Store earlier parent states for explicit backtracking after a stall."""
        for lineage in self.parents:
            self.snapshots.append((self.generation, deepcopy(lineage.candidate)))
        limit = self.cfg.history_depth * self.cfg.max_parents
        if len(self.snapshots) > limit:
            del self.snapshots[:-limit]

    def _add_branch(self):
        """Grow by at most ONE lineage per adjustment. Historical states take priority.

        A near-optimum parent may not yield a diverse child in a single generation;
        try previous generations, a diverse reservoir, then extra proposals.
        """
        cfg = self.cfg
        if len(self.parents) >= cfg.max_parents:
            return False
        incumbent = min((x.candidate for x in self.parents), key=lambda c: c.score)
        def eligible(candidate):
            return (candidate.score <= self.best.score + cfg.absolute_regression
                and all(self.problem.distance(candidate.state, p.candidate.state) >= cfg.min_distance
                        for p in self.parents))
        source = None
        chosen = None
        # Try actual preceding generations (1, 2, 3, ...), not just current offspring.
        for gen, candidate in reversed(self.snapshots):
            if gen < self.generation and eligible(candidate):
                chosen,source = candidate, "history"
                break
        if chosen is None:
            options = [c for c in self.pool if eligible(c)]
            if options:
                chosen = max(options, key=lambda c: (
                    min(self.problem.distance(c.state,p.candidate.state) for p in self.parents),
                    -c.score))
                source = "reservoir"
        attempts = 0
        while chosen is None and attempts < cfg.branch_seed_attempts and self.evaluations < cfg.evaluation_budget:
            attempts += 1
            base = self.rng.choice(self.parents).candidate
            candidate = self._mutate(base, 1.0 + 3.0 * self.rng.random())
            if candidate is not None and eligible(candidate):
                chosen,source = candidate,"generated"
        if chosen is None:
            self.events.append({"generation":self.generation,"event":"population_shortfall",
                "requested":len(self.parents)+1,"created":len(self.parents),"attempts":attempts})
            return False
        self.parents.append(Lineage(deepcopy(chosen),self.generation,[]))
        self.events.append({"generation":self.generation,"event":"population_expand",
            "parents":len(self.parents),"source":source,"attempts":attempts,
            "rollback_generations":self.generation-gen if source=="history" else 0})
        return True

    def _contract(self):
        """Drop one lineage based on BOTH current objective and sustained progress."""
        cfg = self.cfg
        if len(self.parents) <= 1:
            return False
        scores = [p.candidate.score for p in self.parents]
        momentum = [sum(p.progress[-cfg.competition_generations:])
                    / max(1,len(p.progress[-cfg.competition_generations:]))
                    for p in self.parents]
        smin,smax = min(scores),max(scores)
        mmin,mmax = min(momentum),max(momentum)
        ranked = []
        for i,p in enumerate(self.parents):
            quality = (scores[i]-smin)/max(1e-15,smax-smin)
            trend = (momentum[i]-mmin)/max(1e-15,mmax-mmin)
            priority = (1-cfg.trend_weight)*quality - cfg.trend_weight*trend
            ranked.append((priority,i))
        _,drop=max(ranked)
        removed=self.parents.pop(drop)
        self.events.append({"generation":self.generation,"event":"population_contract",
            "parents":len(self.parents),"removed_index":drop,
            "removed_objective":self._objective(removed.candidate.score)})
        # Preserve the global record even when a promising but nonoptimal lineage survives.
        if len(self.parents)==1 and self.best.score < self.parents[0].candidate.score:
            self.snapshots.append((self.generation,deepcopy(self.parents[0].candidate)))
            self.parents[0]=Lineage(deepcopy(self.best),self.generation,[])
        return True

    def _adjust_population(self):
        """Use a LOCAL rolling reference; early giant gains do not set a fixed scale."""
        cfg=self.cfg
        if self.generation-self.checkpoint_step < cfg.population_adjust_interval:
            return
        gain=max(0.0,self.checkpoint_score-self.best.score)
        if self.reference_gain is None:
            self.reference_gain=max(gain,cfg.significant_gain)
        reference=max(self.reference_gain,cfg.significant_gain,1e-15)
        ratio=gain/reference
        if gain <= 0 or ratio < cfg.low_progress_ratio:
            action="expand" if len(self.parents)<cfg.max_parents else "hold"
            if action=="expand":
                self._add_branch()
        elif ratio >= cfg.high_progress_ratio and len(self.parents)>1:
            action="contract"
            self._contract()
        else:
            action="hold"
        self.events.append({"generation":self.generation,"event":"progress_check",
            "gain":gain,"reference":reference,"ratio":ratio,
            "action":action,"parents":len(self.parents)})
        # Adapt to the current stage; zero-gain windows do not erase the reference.
        if gain>0:
            a=cfg.progress_smoothing
            self.reference_gain=(1-a)*self.reference_gain+a*gain
        self.checkpoint_step=self.generation
        self.checkpoint_score=self.best.score

    def _status(self):
        self._atomic("status.json", {
            "generation": self.generation, "evaluations": self.evaluations,
            "best_objective": self._objective(self.best.score),
            "parents": len(self.parents), "competition_end": self.competition_end,
            "progress_reference":self.reference_gain,
            "lineages":[{"born":p.born,"objective":self._objective(p.candidate.score),
                         "trend":sum(p.progress)/max(1,len(p.progress))}
                        for p in self.parents],
            "operator_weights": self.weights,
            "last_event": self.events[-1] if self.events else None,
        })

    def run(self):
        cfg=self.cfg
        initial=self._eval(self.problem.initial(self.rng))
        if initial is None:
            raise ValueError("Initial state must be feasible and have finite objective")
        self.parents=[Lineage(initial,0,[])]
        self._remember(initial)
        self.checkpoint_score=self.best.score
        try:
            for step in range(1,cfg.iterations+1):
                if self.evaluations>=cfg.evaluation_budget:
                    self.events.append({"generation":self.generation,"event":"budget_exhausted"})
                    break
                self.generation=step
                self._remember_history()
                next_parents=[]
                for lineage in self.parents:
                    parent=lineage.candidate
                    improvements=[]
                    for _ in range(cfg.children_per_parent):
                        if self.evaluations>=cfg.evaluation_budget:
                            break
                        child=self._mutate(parent)
                        if child is not None and child.score<parent.score:
                            improvements.append(child)
                    child=min(improvements,key=lambda c:c.score) if improvements else parent
                    lineage.progress.append(max(0.,parent.score-child.score))
                    if len(lineage.progress)>cfg.competition_generations:
                        del lineage.progress[:-cfg.competition_generations]
                    lineage.candidate=child
                    next_parents.append(lineage)
                self.parents=next_parents
                self._adjust_population()
                self.history.append({"generation":step,"evaluations":self.evaluations,
                    "best_objective":self._objective(self.best.score),
                    "parents":len(self.parents),
                    "progress_reference":self.reference_gain})
                if step%cfg.checkpoint_every==0:
                    self._status()
        finally:
            self._save_best()
            if self.best is not None:
                self._status()
                self._atomic("run_summary.json",{
                    "settings":asdict(cfg),"generation":self.generation,
                    "evaluations":self.evaluations,
                    "best_objective":self._objective(self.best.score),
                    "population":len(self.parents),"events":self.events})
        return Result(deepcopy(self.best.state),self._objective(self.best.score),
                      self.evaluations,self.generation,self.history,self.events)
