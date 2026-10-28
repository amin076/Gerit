"""Gerit generic search engine: no assumptions about a particular problem domain."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from copy import deepcopy
from pathlib import Path
import json
import math
import random
import time


@dataclass
class Settings:
    iterations: int = 10000
    children_per_parent: int = 10
    max_parents: int = 5
    initial_parents: int = 1
    stagnation_window: int = 200
    significant_gain: float = 1e-6  # fallback only when no goal/lower-bound is provided
    goal_progress_floor: float = 1e-12
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
    step_scales: tuple = (0.30, 1.0, 3.0)
    step_exploration: float = 0.12
    jump_probability: float = 0.08
    jump_scale: float = 7.0
    lineage_step_learning_rate: float = 0.12
    stagnation_jump_threshold: int = 20
    maximize: bool = False
    seed: int = 2716
    checkpoint_every: int = 200
    log_every: int = 1
    output_dir: str = "results/gerit-core"

    def validate(self, operators):
        for key in ("iterations", "children_per_parent", "max_parents", "stagnation_window",
                    "competition_generations", "evaluation_budget", "reservoir_size",
                    "branch_seed_attempts", "checkpoint_every", "log_every",
                    "population_adjust_interval", "history_depth"):
            if getattr(self, key) < 1:
                raise ValueError(f"{key} must be positive")
        if self.initial_parents>self.max_parents:
            raise ValueError("initial_parents cannot exceed max_parents")
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
        if len(self.step_scales)!=3 or any(
                not math.isfinite(float(x)) or x<=0 for x in self.step_scales):
            raise ValueError("step_scales must contain three positive finite values")
        if not 0 <= self.step_exploration <= 1 or not 0 <= self.jump_probability <= 1:
            raise ValueError("Invalid step exploration/jump probabilities")
        if not math.isfinite(self.jump_scale) or self.jump_scale<=0:
            raise ValueError("Invalid jump_scale")
        if not 0 < self.lineage_step_learning_rate <= 1:
            raise ValueError("Invalid lineage_step_learning_rate")
        if self.stagnation_jump_threshold < 1:
            raise ValueError("stagnation_jump_threshold must be positive")
        for key in ("significant_gain", "goal_progress_floor", "min_distance", "absolute_regression"):
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
    step_weights: list = None  # inherited independent step-size strategy
    stagnation: int = 0
    progress_velocity: float = 0.0
    progress_acceleration: float = 0.0


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

    def __init__(self, problem, operators, settings=None, on_generation=None):
        self.cfg = settings or Settings()
        self.cfg.validate(operators)
        self.problem = problem
        self.on_generation = on_generation  # optional domain-level output observer
        bound = getattr(problem, "objective_lower_bound", None)
        if bound is not None and self.cfg.maximize:
            raise ValueError("objective_lower_bound is supported for minimization only")
        self.goal_score = None if bound is None else (-float(bound) if self.cfg.maximize else float(bound))
        if self.goal_score is not None and not math.isfinite(self.goal_score):
            raise ValueError("objective_lower_bound must be finite")
        self.operators = dict(operators)
        self.rng = random.Random(self.cfg.seed)
        self.weights = {name: 1.0 for name in operators}
        self.step_stats = {label:{"calls":0,"improved":0,"accepted":0}
                           for label in ("small","medium","large","jump")}
        self.operator_stats = {name: {"calls":0,"seconds":0.0,"valid":0,"improved":0}
                               for name in operators}
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
        self.previous_goal_gap = None
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
        if len(self.pool) < cfg.reservoir_size:
            self.pool.append(deepcopy(candidate))
            return
        # O(N) memory admission: avoid repeated all-pairs O(N^2) diversity scans.
        # Keep the archive (self.best) separately and retain a mix of quality
        # and novelty in this bounded reservoir.
        if not self.pool:
            return
        nearest = min(range(len(self.pool)),
                      key=lambda i: self.problem.distance(candidate.state,self.pool[i].state))
        worst = max(range(len(self.pool)),key=lambda i:self.pool[i].score)
        if candidate.score < self.pool[nearest].score:
            self.pool[nearest] = deepcopy(candidate)
        elif candidate.score < self.pool[worst].score:
            self.pool[worst] = deepcopy(candidate)
        # Otherwise reject; no global pairwise distance recomputation.

    def _mutate(self, parent, intensity=1.0, *, with_feedback=False):
        names = list(self.operators)
        total = sum(self.weights.values())
        floor = self.cfg.exploration_floor
        probs = [(1-floor)*self.weights[n]/total + floor/len(names) for n in names]
        name = self.rng.choices(names, weights=probs, k=1)[0]
        t0=time.perf_counter()
        state = self.operators[name](deepcopy(parent.state), self.rng, intensity)
        self.operator_stats[name]["seconds"] += time.perf_counter()-t0
        self.operator_stats[name]["calls"] += 1
        child = self._eval(state)
        if child is not None:
            self.operator_stats[name]["valid"] += 1
            if child.score < parent.score:
                self.operator_stats[name]["improved"] += 1
        if child is not None:
            self._remember(child)
        reward = 1.0 if child is not None and child.score < parent.score else 0.0
        rate = self.cfg.learning_rate
        self.weights[name] = max(0.02, (1-rate)*self.weights[name] + rate*(0.02+reward))
        if with_feedback:
            return child, name
        return child

    def _sample_step(self,lineage):
        """A domain-free mutation intensity drawn from inheritable preferences."""
        if lineage.step_weights is None:
            lineage.step_weights=[1.,1.,1.]
        w=lineage.step_weights
        floor=self.cfg.step_exploration
        probabilities=[(1-floor)*x/sum(w)+floor/3 for x in w]
        k=self.rng.choices(range(3),weights=probabilities,k=1)[0]
        return k,self.cfg.step_scales[k]

    def _step_feedback(self,lineage,index,parent,child):
        label=("small","medium","large")[index]
        stat=self.step_stats[label]
        stat["calls"]+=1
        win=(child is not None and child.score<parent.score)
        if win:
            stat["improved"]+=1
        # Reward relative to the parent's own objective magnitude, not units.
        reward=0.
        if win:
            improvement=(parent.score-child.score)/max(1.,abs(parent.score))
            reward=min(1.,0.20+10.*improvement)
        rate=self.cfg.lineage_step_learning_rate
        lineage.step_weights[index]=max(0.05,(1-rate)*lineage.step_weights[index]+rate*(0.05+reward))

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
        # Branch strategies inherit from an existing lineage. Search policy is
        # separate from the domain-specific candidate state.
        ancestor=min(self.parents,key=lambda p:self.problem.distance(chosen.state,p.candidate.state))
        inherited=list(ancestor.step_weights or [1.,1.,1.])
        self.parents.append(Lineage(deepcopy(chosen),self.generation,[],
                                    step_weights=inherited))
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
        """Problem-independent progress controller.

        If a valid objective lower bound is declared, use fraction of the
        remaining *certified* objective gap closed in the last window.
        Otherwise compare consecutive positive gains on a moving local scale.
        Neither square geometry nor units are known to this engine.
        """
        cfg=self.cfg
        if self.generation-self.checkpoint_step < cfg.population_adjust_interval:
            return
        gain=max(0.,self.checkpoint_score-self.best.score)
        gap=None
        if self.goal_score is not None:
            gap=max(0.,self.checkpoint_score-self.goal_score)
            if self.best.score < self.goal_score-1e-9*max(1.,abs(self.goal_score)):
                raise ValueError("Problem objective fell below its asserted lower bound")
            progress_fraction=gain/max(gap,cfg.goal_progress_floor)
            if self.reference_gain is None:
                self.reference_gain=max(progress_fraction,cfg.goal_progress_floor)
            reference=self.reference_gain
            ratio=progress_fraction/max(reference,cfg.goal_progress_floor)
            progress_mode="bound_fraction"
        else:
            if self.reference_gain is None:
                self.reference_gain=gain if gain>0 else max(cfg.significant_gain,1e-300)
            reference=max(self.reference_gain,1e-300)
            ratio=gain/reference
            progress_mode="rolling_gain"
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
            "progress_mode":progress_mode,"goal_gap":gap,
            "action":action,"parents":len(self.parents)})
        alpha=cfg.progress_smoothing
        if self.goal_score is not None:
            # Decay even through stalls: an early big win must not dominate forever.
            self.reference_gain=(1-alpha)*self.reference_gain+alpha*progress_fraction
        elif gain>0:
            self.reference_gain=(1-alpha)*self.reference_gain+alpha*gain
        self.checkpoint_step=self.generation
        self.checkpoint_score=self.best.score

    def _status(self):
        self._atomic("status.json", {
            "generation": self.generation, "evaluations": self.evaluations,
            "best_objective": self._objective(self.best.score),
            "parents": len(self.parents), "competition_end": self.competition_end,
            "progress_reference":self.reference_gain,
            "goal_gap":None if self.goal_score is None else max(0.,self.best.score-self.goal_score),
            "lineages":[{"born":p.born,"objective":self._objective(p.candidate.score),
                         "trend":sum(p.progress)/max(1,len(p.progress)),
                         "step_weights":p.step_weights,
                         "progress_velocity":p.progress_velocity,
                         "progress_acceleration":p.progress_acceleration,
                         "stagnation":p.stagnation}
                        for p in self.parents],
            "operator_weights": self.weights,
            "operator_stats":self.operator_stats,
            "step_stats":self.step_stats,
            "last_event": self.events[-1] if self.events else None,
        })

    def run(self):
        cfg=self.cfg
        initial=self._eval(self.problem.initial(self.rng))
        if initial is None:
            raise ValueError("Initial state must be feasible and have finite objective")
        self.parents=[Lineage(initial,0,[],step_weights=[1.,1.,1.])]
        self._remember(initial)
        # Optional initial exploratory population: newly seeded lineages
        # inherit independent policy copies, while best-ever remains protected.
        if cfg.initial_parents>1:
            for _ in range(cfg.initial_parents-1):
                if self.evaluations>=cfg.evaluation_budget:
                    break
                self._add_branch()
        self.checkpoint_score=self.best.score
        if self.goal_score is not None and self.best.score < self.goal_score-1e-9*max(1.,abs(self.goal_score)):
            raise ValueError("Initial objective violates the stated objective lower bound")
        if self.on_generation is not None:
            self.on_generation(0,deepcopy(self.best.state),self._objective(self.best.score),len(self.parents),self.evaluations)
        started_at=time.perf_counter()
        previous_best=self._objective(self.best.score)
        print(f"START generations={cfg.iterations} initial_best={previous_best:.12f} "
              f"children={cfg.children_per_parent} max_parents={cfg.max_parents} "
              f"evaluation_budget={cfg.evaluation_budget}",flush=True)
        try:
            for step in range(1,cfg.iterations+1):
                if self.evaluations>=cfg.evaluation_budget:
                    self.events.append({"generation":self.generation,"event":"budget_exhausted"})
                    break
                self.generation=step
                generation_started=time.perf_counter()
                previous_best=self._objective(self.best.score)
                self._remember_history()
                next_parents=[]
                for lineage in self.parents:
                    parent=lineage.candidate
                    improvements=[]
                    for _ in range(cfg.children_per_parent):
                        if self.evaluations>=cfg.evaluation_budget:
                            break
                        k,intensity=self._sample_step(lineage)
                        child=self._mutate(parent,intensity)
                        self._step_feedback(lineage,k,parent,child)
                        if child is not None and child.score<parent.score:
                            improvements.append(child)
                    # A continuous, explicit chance to test a much longer jump,
                    # even after local progress has stopped. Archive the best
                    # objective independently of the chosen lineage.
                    jump_chance=cfg.jump_probability
                    if lineage.stagnation>=cfg.stagnation_jump_threshold:
                        jump_chance=min(0.5,2*jump_chance)
                    if self.evaluations<cfg.evaluation_budget and self.rng.random()<jump_chance:
                        self.step_stats["jump"]["calls"]+=1
                        trial=self._mutate(parent,cfg.jump_scale)
                        if trial is not None and trial.score<parent.score:
                            self.step_stats["jump"]["improved"]+=1
                            improvements.append(trial)
                        elif (trial is not None
                              and trial.score<=self.best.score+cfg.absolute_regression
                              and len(self.parents)>1
                              and self.rng.random()<0.20):
                            # Limited non-improving lineage exploration, never
                            # overwrites the global best. This branch may move
                            # into a different basin on the next generation.
                            self.snapshots.append((step,deepcopy(trial)))
                            self.step_stats["jump"]["accepted"]+=1
                    child=min(improvements,key=lambda c:c.score) if improvements else parent
                    gain=max(0.,parent.score-child.score)
                    # First difference of progress and its discrete acceleration.
                    prev_gain=lineage.progress[-1] if lineage.progress else 0.
                    prev_velocity=lineage.progress_velocity
                    lineage.progress_velocity=gain-prev_gain
                    lineage.progress_acceleration=lineage.progress_velocity-prev_velocity
                    lineage.stagnation=0 if gain>0 else lineage.stagnation+1
                    lineage.progress.append(gain)
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
                if self.on_generation is not None:
                    self.on_generation(step,deepcopy(self.best.state),
                        self._objective(self.best.score),len(self.parents),self.evaluations)
                if step%cfg.checkpoint_every==0:
                    self._status()
                if step==1 or step%cfg.log_every==0:
                    current_best=self._objective(self.best.score)
                    improvement=(previous_best-current_best) if not cfg.maximize else (current_best-previous_best)
                    print(f"STEP {step}/{cfg.iterations} "
                          f"best_objective={current_best:.12f} "
                          f"delta_objective={max(0.,improvement):.12f} "
                          f"parents={len(self.parents)} "
                          f"evaluations={self.evaluations}/{cfg.evaluation_budget} "
                          f"generation_seconds={time.perf_counter()-generation_started:.1f} "
                          f"elapsed_seconds={time.perf_counter()-started_at:.1f}",flush=True)
        finally:
            self._save_best()
            if self.best is not None:
                self._status()
                self._atomic("run_summary.json",{
                    "settings":asdict(cfg),"generation":self.generation,
                    "evaluations":self.evaluations,
                    "best_objective":self._objective(self.best.score),
                    "population":len(self.parents),"events":self.events,
                    "operator_stats":self.operator_stats,
                    "step_stats":self.step_stats})
        return Result(deepcopy(self.best.state),self._objective(self.best.score),
                      self.evaluations,self.generation,self.history,self.events)
