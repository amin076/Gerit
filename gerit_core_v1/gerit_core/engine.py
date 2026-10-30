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
    max_parents: int = 10  # maximum active lineages; starts with one
    initial_parents: int = 1
    stagnation_window: int = 200
    significant_gain: float = 1e-6  # fallback only when no goal/lower-bound is provided
    goal_progress_floor: float = 1e-12
    competition_generations: int = 200  # lineage trend memory horizon (legacy CLI flag)
    population_adjust_interval: int = 20
    history_depth: int = 120
    adaptive_historical: bool = False
    max_forward_branches: int = 5
    max_historical_branches: int = 5
    historical_lookback_min: int = 100
    historical_lookback_max: int = 1500
    historical_trial_generations: int = 300
    historical_spawn_interval: int = 100
    historical_archive_interval: int = 20
    historical_archive_capacity: int = 320
    historical_stall_windows: int = 2
    historical_structural_weight: float = 0.5
    historical_age_weight: float = 0.3
    historical_quality_weight: float = 0.2
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
    diversity_fraction: float = 0.10  # fraction of observed candidate spread
    explorer_generations: int = 15
    max_explorers: int = 2
    explorer_uphill_probability: float = 0.20
    learning_prior_trials: float = 20.0
    learning_prior_successes: float = 0.2
    recent_learning_window: int = 120
    recent_learning_mix: float = 0.45
    utility_gain_scale: float = 25.0
    delayed_credit_scale: float = 0.5
    maximize: bool = False
    seed: int = 2716
    checkpoint_every: int = 200
    log_every: int = 10
    output_dir: str = "results/gerit-core"

    def validate(self, operators):
        for key in ("iterations", "children_per_parent", "max_parents", "stagnation_window",
                    "competition_generations", "evaluation_budget", "reservoir_size",
                    "branch_seed_attempts", "checkpoint_every", "log_every",
                    "population_adjust_interval", "history_depth"):
            if getattr(self, key) < 1:
                raise ValueError(f"{key} must be positive")
        if self.adaptive_historical:
            for key in ("max_forward_branches","max_historical_branches",
                        "historical_lookback_min","historical_lookback_max",
                        "historical_trial_generations","historical_spawn_interval",
                        "historical_archive_interval","historical_archive_capacity",
                        "historical_stall_windows"):
                if getattr(self,key)<1:
                    raise ValueError(f"{key} must be positive")
            if self.max_forward_branches+self.max_historical_branches>self.max_parents:
                raise ValueError("forward + historical slots exceed max_parents")
            if self.initial_parents>self.max_forward_branches:
                raise ValueError("initial_parents exceeds forward slots")
            if self.historical_lookback_max<self.historical_lookback_min:
                raise ValueError("historical lookback maximum must exceed minimum")
            weights=(self.historical_structural_weight,self.historical_age_weight,
                     self.historical_quality_weight)
            if any(not math.isfinite(w) or w<0 for w in weights) or sum(weights)<=0:
                raise ValueError("Historical weights must be nonnegative and nonzero")
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
        if not 0 <= self.diversity_fraction <= 1:
            raise ValueError("diversity_fraction must be in [0,1]")
        if self.explorer_generations < 1 or self.max_explorers < 0:
            raise ValueError("Invalid explorer horizon or capacity")
        if not 0 <= self.explorer_uphill_probability <= 1:
            raise ValueError("Invalid explorer_uphill_probability")
        if not (math.isfinite(self.learning_prior_trials)
                and math.isfinite(self.learning_prior_successes)
                and self.learning_prior_trials>0
                and 0<self.learning_prior_successes<self.learning_prior_trials):
            raise ValueError("Invalid learning prior")
        if self.recent_learning_window < 1:
            raise ValueError("recent_learning_window must be positive")
        if not 0<=self.recent_learning_mix<=1 or self.utility_gain_scale<=0 or self.delayed_credit_scale<0:
            raise ValueError("Invalid utility learning settings")
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
    node_id: int = 0
    parent_node_id: int = None


@dataclass
class Lineage:
    candidate: Candidate
    born: int
    progress: list  # improvement against its own parent, one value per generation
    step_weights: list = None  # posterior mean success rates; inherited
    step_attempts: list = None
    step_successes: list = None
    stagnation: int = 0
    progress_velocity: float = 0.0
    progress_acceleration: float = 0.0
    explorer_until: int = 0
    explorer_baseline: float = 0.0
    explorer_birth_score: float = 0.0
    explorer_origin_operator: str = ""
    explorer_origin_intensity: float = 0.0
    lineage_id: int = 0
    parent_lineage_id: int = 0
    explorer_credit_baseline: float = 0.0
    explorer_credited: bool = False
    branch_kind: str = "forward"
    historical_protected_until: int = 0
    historical_start_score: float = 0.0
    historical_birth_generation: int = 0


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
        self.next_lineage_id = 1
        self.next_node_id = 1
        self.written_node_ids = set()
        self.genealogy_path = None
        self.best_origin = None
        self.best_records = []
        self.late_credit_events = []
        self.operator_memory = {name:{"attempts":0,"successes":0,
                                      "utility_sum":0.0,"recent_utilities":[],
                                      "delayed_credit":0.0}
                                for name in operators}
        self.explorer_stats = {"spawned":0,"expired":0,"improved_baseline":0,
                               "uphill_steps":0,"rejected_duplicate":0,
                               "rejected_capacity":0}
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
        self.snapshots = []          # recent historical parent states
        self.historical_archive = []
        self.historical_used_node_ids = set()
        self.historical_last_spawn = -10**9
        self.historical_weak_windows = 0
        self.historical_stats = {"spawned":0,"promoted":0,"expired":0,
                                 "rejected_duplicate":0,"insufficient_history":0}
        self.historical_last_archive_generation = -1
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

    def _write_genealogy(self, candidate, kind="accepted"):
        """Persist only selected candidates and records, with exact causal parent IDs.

        Intermediate rejected mutations get IDs but no serialized geometry.
        Their accepted descendants can only arise through an accepted parent,
        so the chain back to the initial state remains complete.
        """
        if candidate.node_id in self.written_node_ids:
            return
        self.written_node_ids.add(candidate.node_id)
        if self.genealogy_path is None:
            return
        row={"node_id":candidate.node_id,
             "parent_node_id":candidate.parent_node_id,
             "generation":self.generation,
             "evaluation":self.evaluations,
             "objective":self._objective(candidate.score),
             "kind":kind,
             "state":self.problem.encode(candidate.state)}
        with self.genealogy_path.open("a",encoding="utf8") as file:
            file.write(json.dumps(row,ensure_ascii=False,separators=(",",":"))+"\\n")

    def _save_best(self):
        if self.best is not None:
            self._atomic("best.json", {
                "generation": self.generation, "evaluations": self.evaluations,
                "objective": self._objective(self.best.score),
                "state": self.problem.encode(self.best.state),
                "origin": self.best_origin,
                "best_node_id": self.best.node_id
            })

    def _eval(self, state, origin=None, parent_node_id=None):
        if self.evaluations >= self.cfg.evaluation_budget:
            return None
        self.evaluations += 1
        if not self.problem.feasible(state):
            return None
        value = float(self.problem.evaluate(state))
        if not math.isfinite(value):
            return None
        candidate = Candidate(deepcopy(state), -value if self.cfg.maximize else value,
                              self.next_node_id, parent_node_id)
        self.next_node_id += 1
        if self.best is None or candidate.score < self.best.score:
            previous=None if self.best is None else self.best.score
            self.best = deepcopy(candidate)
            self.best_origin=dict(origin or {"type":"initial","lineage_id":None,
                                             "operator":None,"intensity":None})
            record={"generation":self.generation,"evaluation":self.evaluations,
                    "objective":self._objective(candidate.score),
                    "previous_objective":None if previous is None else self._objective(previous),
                    **self.best_origin}
            record["node_id"]=candidate.node_id
            record["parent_node_id"]=candidate.parent_node_id
            self.best_records.append(record)
            self.events.append({"event":"best_record",**record})
            self._write_genealogy(candidate,"best_record")
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

    def _success_rate(self,attempts,successes):
        """Smoothed empirical reward with fixed prior; keeps rare wins in memory."""
        return ((self.cfg.learning_prior_successes+successes) /
                (self.cfg.learning_prior_trials+attempts))

    def _new_lineage(self,candidate,born,ancestor=None):
        if ancestor is None:
            attempts=[0,0,0]
            successes=[0,0,0]
        else:
            attempts=list(ancestor.step_attempts or [0,0,0])
            successes=list(ancestor.step_successes or [0,0,0])
        weights=[self._success_rate(a,w) for a,w in zip(attempts,successes)]
        identity=self.next_lineage_id
        self.next_lineage_id+=1
        return Lineage(deepcopy(candidate),born,[],step_weights=weights,
                       step_attempts=attempts,step_successes=successes,
                       lineage_id=identity,
                       parent_lineage_id=ancestor.lineage_id if ancestor else 0)

    def _operator_preference(self,name):
        """Blend long-term quality/cost evidence with a bounded recent window."""
        m=self.operator_memory[name]
        prior=self.cfg.learning_prior_trials
        base=self.cfg.learning_prior_successes/prior
        long=(self.cfg.learning_prior_successes+m["utility_sum"])/(prior+m["attempts"])
        recent=m["recent_utilities"]
        short=(self.cfg.learning_prior_successes+sum(recent))/(prior+len(recent))
        return max(1e-12,(1-self.cfg.recent_learning_mix)*long+
                   self.cfg.recent_learning_mix*short)

    def _credit_operator(self,name,amount):
        """Delayed credit for the *originating* jump, not every later step."""
        if not name or name not in self.operator_memory or amount<=0:
            return
        m=self.operator_memory[name]
        credit=min(self.cfg.delayed_credit_scale,amount*self.cfg.delayed_credit_scale)
        m["utility_sum"]+=credit
        m["delayed_credit"]+=credit
        # Add to recent history without fabricating an extra operator call.
        m["recent_utilities"].append(credit)
        del m["recent_utilities"][:-self.cfg.recent_learning_window]
        self.weights[name]=self._operator_preference(name)

    def _mutate(self, parent, intensity=1.0, *, return_operator=False, lineage=None,
                move_type="regular"):
        names = list(self.operators)
        total = sum(self.weights.values())
        floor = self.cfg.exploration_floor
        probs = [(1-floor)*self.weights[n]/total + floor/len(names) for n in names]
        name = self.rng.choices(names, weights=probs, k=1)[0]
        t0=time.perf_counter()
        state = self.operators[name](deepcopy(parent.state), self.rng, intensity)
        elapsed=max(0.,time.perf_counter()-t0)
        self.operator_stats[name]["seconds"] += elapsed
        self.operator_stats[name]["calls"] += 1
        origin={"type":move_type,"lineage_id":lineage.lineage_id if lineage else None,
                "operator":name,"intensity":intensity,
                "parent_score":self._objective(parent.score),
                "originating_operator":lineage.explorer_origin_operator if lineage else ""}
        child = self._eval(state,origin=origin,parent_node_id=parent.node_id)
        if child is not None:
            self.operator_stats[name]["valid"] += 1
            if child.score < parent.score:
                self.operator_stats[name]["improved"] += 1
        if child is not None:
            self._remember(child)
        improved=(child is not None and child.score < parent.score)
        memory=self.operator_memory[name]
        memory["attempts"]+=1
        memory["successes"]+=int(improved)
        # Relative magnitude makes the reward unitless; measured operator
        # runtime penalizes expensive actions, using an observed global
        # reference rather than any problem-specific conversion factor.
        total_seconds=sum(v["seconds"] for v in self.operator_stats.values())
        total_calls=sum(v["calls"] for v in self.operator_stats.values())
        reference_seconds=max(1e-8,total_seconds/max(1,total_calls))
        utility=0.0
        if improved:
            gain=(parent.score-child.score)/max(1.,abs(parent.score))
            quality=min(1.,0.10+self.cfg.utility_gain_scale*gain)
            utility=quality/(1.+elapsed/reference_seconds)
        memory["utility_sum"]+=utility
        memory["recent_utilities"].append(utility)
        del memory["recent_utilities"][:-self.cfg.recent_learning_window]
        self.weights[name]=self._operator_preference(name)
        return (child,name) if return_operator else child

    def _sample_step(self,lineage):
        """A domain-free mutation intensity drawn from inheritable preferences."""
        if lineage.step_weights is None:
            lineage.step_attempts=[0,0,0]
            lineage.step_successes=[0,0,0]
            lineage.step_weights=[self._success_rate(0,0)]*3
        w=lineage.step_weights
        floor=self.cfg.step_exploration
        probabilities=[(1-floor)*x/sum(w)+floor/3 for x in w]
        # Discrete first/second differences of recent improvement help detect
        # deteriorating progress; they are not derivatives of the objective
        # or coordinates of the underlying problem.
        if (lineage.stagnation>=self.cfg.stagnation_jump_threshold
                or (lineage.progress_velocity<0 and lineage.progress_acceleration<0)):
            probabilities=[probabilities[0],probabilities[1],probabilities[2]*1.8]
        elif (lineage.progress_velocity<0 and lineage.progress_acceleration>0):
            probabilities=[probabilities[0]*1.25,probabilities[1],probabilities[2]]
        k=self.rng.choices(range(3),weights=probabilities,k=1)[0]
        return k,self.cfg.step_scales[k]

    def _step_feedback(self,lineage,index,parent,child):
        label=("small","medium","large")[index]
        stat=self.step_stats[label]
        stat["calls"]+=1
        win=(child is not None and child.score<parent.score)
        if win:
            stat["improved"]+=1
        # Record immediate improvement evidence; magnitude/delayed credit
        # can be introduced separately without changing the domain interface.
        if lineage.step_attempts is None:
            lineage.step_attempts=[0,0,0]
            lineage.step_successes=[0,0,0]
        lineage.step_attempts[index]+=1
        lineage.step_successes[index]+=int(win)
        lineage.step_weights[index]=self._success_rate(
            lineage.step_attempts[index],lineage.step_successes[index])

    def _distance(self,a,b):
        value=float(self.problem.distance(a.state,b.state))
        if not math.isfinite(value) or value<0:
            raise ValueError("problem.distance must be finite and nonnegative")
        return value

    def _diversity_threshold(self):
        """Scale a threshold using observed variation, never geometry units."""
        if self.best is None or not self.pool:
            return self.cfg.min_distance
        distances=sorted(self._distance(self.best,c) for c in self.pool)
        # Median prevents one extreme/outlier from setting the scale.
        median=distances[len(distances)//2]
        return max(self.cfg.min_distance,self.cfg.diversity_fraction*median)

    def _population_diversity(self):
        distances=[self._distance(a.candidate,b.candidate)
                   for i,a in enumerate(self.parents) for b in self.parents[i+1:]]
        if not distances:
            return {"minimum":None,"mean":None,"maximum":None,
                    "threshold":self._diversity_threshold(),"pairs":0}
        return {"minimum":min(distances),"mean":sum(distances)/len(distances),
                "maximum":max(distances),"threshold":self._diversity_threshold(),
                "pairs":len(distances)}

    def _explorer_active(self,lineage):
        return lineage.explorer_until>self.generation

    def _spawn_explorer(self,candidate,ancestor,origin_operator="",origin_intensity=0.):
        """Give a distinct, temporarily worse jump an independent multi-gen path."""
        cfg=self.cfg
        active=sum(self._explorer_active(p) for p in self.parents)
        if (len(self.parents)>=cfg.max_parents or active>=cfg.max_explorers
                or (cfg.adaptive_historical and
                    self._forward_count()>=cfg.max_forward_branches)):
            self.explorer_stats["rejected_capacity"]+=1
            return False
        threshold=self._diversity_threshold()
        if any(self._distance(candidate,p.candidate)<threshold for p in self.parents):
            self.explorer_stats["rejected_duplicate"]+=1
            return False
        if candidate.score>self.best.score+cfg.absolute_regression:
            return False
        explorer=self._new_lineage(candidate,self.generation,ancestor)
        explorer.explorer_until=self.generation+cfg.explorer_generations
        explorer.explorer_baseline=ancestor.candidate.score
        explorer.explorer_birth_score=candidate.score
        explorer.explorer_origin_operator=origin_operator
        explorer.explorer_origin_intensity=origin_intensity
        explorer.explorer_credit_baseline=ancestor.candidate.score
        self.parents.append(explorer)
        self._write_genealogy(candidate,"explorer_seed")
        self.explorer_stats["spawned"]+=1
        self.events.append({"generation":self.generation,"event":"explorer_spawn",
            "parents":len(self.parents),"horizon":cfg.explorer_generations,
            "regression":candidate.score-ancestor.candidate.score,
            "origin_operator":origin_operator,
            "lineage_id":explorer.lineage_id,
            "parent_lineage_id":ancestor.lineage_id,
            "minimum_distance":min(self._distance(candidate,p.candidate)
                                  for p in self.parents[:-1])})
        return True

    def _credit_late_explorer(self,lineage,score):
        """One reward after trial expiry, when a living explorer beats its baseline."""
        if (not lineage.explorer_origin_operator or lineage.explorer_until!=0
                or lineage.explorer_credited
                or score>=lineage.explorer_credit_baseline):
            return False
        gain=(lineage.explorer_credit_baseline-score)/max(
            1.,abs(lineage.explorer_credit_baseline))
        amount=min(1.,self.cfg.utility_gain_scale*gain)
        self._credit_operator(lineage.explorer_origin_operator,amount)
        lineage.explorer_credited=True
        event={"generation":self.generation,"event":"explorer_late_success",
               "lineage_id":lineage.lineage_id,
               "origin_operator":lineage.explorer_origin_operator,
               "baseline":lineage.explorer_credit_baseline,
               "final_score":score,"credit_input":amount}
        self.events.append(event)
        self.late_credit_events.append(event)
        return True

    def _remember_history(self):
        """Store earlier parent states for explicit backtracking after a stall."""
        for lineage in self.parents:
            self.snapshots.append((self.generation, deepcopy(lineage.candidate)))
        self._archive_historical_states()
        limit = self.cfg.history_depth * self.cfg.max_parents
        if len(self.snapshots) > limit:
            del self.snapshots[:-limit]

    def _archive_historical_states(self):
        """Keep a bounded, spaced archive of real old parent states."""
        cfg=self.cfg
        if not cfg.adaptive_historical or self.generation==self.historical_last_archive_generation:
            return
        if self.generation % cfg.historical_archive_interval:
            return
        self.historical_last_archive_generation=self.generation
        sample=min(self.parents,key=lambda p:p.candidate.score).candidate
        self.historical_archive.append((self.generation,deepcopy(sample)))
        if len(self.historical_archive)>cfg.historical_archive_capacity:
            archive=self.historical_archive
            self.historical_archive=[archive[0]]+archive[2::2]
            self.historical_archive=self.historical_archive[-cfg.historical_archive_capacity:]

    def _historical_count(self):
        return sum(p.branch_kind=="historical" for p in self.parents)

    def _forward_count(self):
        return sum(p.branch_kind!="historical" for p in self.parents)

    def _promote_or_expire_historical(self):
        """Protect a historical path for its entire trial, then reallocate."""
        if not self.cfg.adaptive_historical:
            return
        for p in list(self.parents):
            if p.branch_kind!="historical" or self.generation<p.historical_protected_until:
                continue
            if (p.candidate.score<=self.best.score+self.cfg.absolute_regression
                    and self._forward_count()<self.cfg.max_forward_branches):
                p.branch_kind="forward"
                p.historical_protected_until=0
                self.historical_stats["promoted"]+=1
                self.events.append({"generation":self.generation,"event":"historical_promote",
                                    "lineage_id":p.lineage_id})
            else:
                self.parents.remove(p)
                self.historical_stats["expired"]+=1
                self.events.append({"generation":self.generation,"event":"historical_expire",
                                    "branch_kind":p.branch_kind,
                         "historical_protected_until":p.historical_protected_until,
                         "historical_birth_generation":p.historical_birth_generation,
                         "lineage_id":p.lineage_id,
                                    "initial_score":self._objective(p.historical_start_score),
                                    "final_score":self._objective(p.candidate.score)})
        if not self.parents:
            self.parents=[self._new_lineage(self.best,self.generation)]

    def _spawn_historical_branch(self):
        """Pick a structurally novel, old checkpoint, ignoring current quality cutoffs."""
        cfg=self.cfg
        if not cfg.adaptive_historical or self._historical_count()>=cfg.max_historical_branches:
            return False
        if len(self.parents)>=cfg.max_parents:
            return False
        options=[]
        for born,candidate in self.historical_archive:
            age=self.generation-born
            if not cfg.historical_lookback_min<=age<=cfg.historical_lookback_max:
                continue
            if candidate.node_id in self.historical_used_node_ids:
                continue
            distances=[self._distance(candidate,p.candidate) for p in self.parents]
            if not distances or min(distances)<self._diversity_threshold():
                self.historical_stats["rejected_duplicate"]+=1
                continue
            options.append((born,candidate,min(distances)))
        if not options:
            self.historical_stats["insufficient_history"]+=1
            self.events.append({"generation":self.generation,"event":"historical_shortfall"})
            return False
        ds=[d for _,_,d in options]
        scores=[c.score for _,c,_ in options]
        def norm(v,lo,hi):
            return (v-lo)/(hi-lo) if hi>lo else 0.5
        weights=(cfg.historical_structural_weight,cfg.historical_age_weight,
                 cfg.historical_quality_weight)
        def priority(item):
            gen,candidate,d=item
            age=self.generation-gen
            return (weights[0]*norm(d,min(ds),max(ds))
                    +weights[1]*(age-cfg.historical_lookback_min)
                    /max(1,cfg.historical_lookback_max-cfg.historical_lookback_min)
                    +weights[2]*(1-norm(candidate.score,min(scores),max(scores))))
        born,chosen,distance=max(options,key=priority)
        revived=self._new_lineage(chosen,self.generation) # independent step preferences
        revived.branch_kind="historical"
        revived.historical_protected_until=self.generation+cfg.historical_trial_generations
        revived.historical_start_score=chosen.score
        revived.historical_birth_generation=born
        self.parents.append(revived)
        self._write_genealogy(chosen,"historical_revive")
        self.historical_used_node_ids.add(chosen.node_id)
        self.historical_last_spawn=self.generation
        self.historical_stats["spawned"]+=1
        self.events.append({"generation":self.generation,"event":"historical_spawn",
                            "lineage_id":revived.lineage_id,"seed_node_id":chosen.node_id,
                            "from_generation":born,"rollback_generations":self.generation-born,
                            "distance":distance,
                            "protected_until":revived.historical_protected_until,
                            "parents":len(self.parents)})
        return True

    def _add_branch(self):
        """Grow by at most ONE lineage per adjustment. Historical states take priority.

        A near-optimum parent may not yield a diverse child in a single generation;
        try previous generations, a diverse reservoir, then extra proposals.
        """
        cfg = self.cfg
        if len(self.parents) >= cfg.max_parents or (cfg.adaptive_historical and self._forward_count()>=cfg.max_forward_branches):
            return False
        incumbent = min((x.candidate for x in self.parents), key=lambda c: c.score)
        threshold=self._diversity_threshold()
        def eligible(candidate):
            return (candidate.score <= self.best.score + cfg.absolute_regression
                and all(self._distance(candidate,p.candidate) >= threshold
                        for p in self.parents))
        source = None
        chosen = None
        # Try actual preceding generations (1, 2, 3, ...), not just current offspring.
        # Prefer a genuinely different historical path over the newest
        # almost-identical past parent.
        history=[(gen,c) for gen,c in self.snapshots
                 if gen < self.generation and eligible(c)]
        if history:
            gen,chosen=max(history,key=lambda item:(
                min(self._distance(item[1],p.candidate) for p in self.parents),
                -item[1].score,item[0]))
            source="history"
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
        self.parents.append(self._new_lineage(chosen,self.generation,ancestor))
        self._write_genealogy(chosen,"branch_seed")
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
            if self._explorer_active(p) or (p.branch_kind=="historical" and self.generation<p.historical_protected_until):
                continue  # protected trial cannot be discarded early
            ranked.append((priority,i))
        if not ranked:
            return False
        _,drop=max(ranked)
        removed=self.parents.pop(drop)
        self.events.append({"generation":self.generation,"event":"population_contract",
            "parents":len(self.parents),"removed_index":drop,
            "removed_objective":self._objective(removed.candidate.score)})
        # Preserve the global record even when a promising but nonoptimal lineage survives.
        if (len(self.parents)==1 and not self._explorer_active(self.parents[0])
                and self.best.score < self.parents[0].candidate.score):
            self.snapshots.append((self.generation,deepcopy(self.parents[0].candidate)))
            self.parents[0]=self._new_lineage(self.best,self.generation,self.parents[0])
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
        weak=(gain<=0 or ratio<cfg.low_progress_ratio)
        self.historical_weak_windows=self.historical_weak_windows+1 if weak else 0
        if cfg.adaptive_historical:
            self._promote_or_expire_historical()
        if weak:
            action="hold"
            if (cfg.adaptive_historical
                    and self._forward_count()>=cfg.max_forward_branches
                    and self.historical_weak_windows>=cfg.historical_stall_windows
                    and self.generation-self.historical_last_spawn>=cfg.historical_spawn_interval
                    and self._spawn_historical_branch()):
                action="historical_expand"
            elif self._add_branch():
                action="expand"
            elif (cfg.adaptive_historical
                    and self.historical_weak_windows>=cfg.historical_stall_windows
                    and self.generation-self.historical_last_spawn>=cfg.historical_spawn_interval
                    and self._spawn_historical_branch()):
                action="historical_expand"
        elif ratio>=cfg.high_progress_ratio and len(self.parents)>1:
            action="contract" if self._contract() else "hold"
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
                         "step_attempts":p.step_attempts,
                         "step_successes":p.step_successes,
                         "progress_velocity":p.progress_velocity,
                         "progress_acceleration":p.progress_acceleration,
                         "stagnation":p.stagnation,
                         "explorer_until":p.explorer_until,
                         "explorer_baseline":p.explorer_baseline,
                         "explorer_origin_operator":p.explorer_origin_operator,
                         "lineage_id":p.lineage_id,
                         "parent_lineage_id":p.parent_lineage_id,
                         "explorer_credited":p.explorer_credited}
                        for p in self.parents],
            "operator_weights": self.weights,
            "best_origin":self.best_origin,
            "best_record_count":len(self.best_records),
            "late_credit_events":self.late_credit_events,
            "historical_stats":self.historical_stats,
            "historical_archive_count":len(self.historical_archive),
            "operator_memory": self.operator_memory,
            "operator_stats":self.operator_stats,
            "step_stats":self.step_stats,
            "explorer_stats":self.explorer_stats,
            "population_diversity":self._population_diversity(),
            "last_event": self.events[-1] if self.events else None,
        })

    def run(self):
        cfg=self.cfg
        self.genealogy_path=self.output/"genealogy.jsonl"
        self.genealogy_path.write_text("",encoding="utf8")
        initial=self._eval(self.problem.initial(self.rng))
        if initial is None:
            raise ValueError("Initial state must be feasible and have finite objective")
        self.parents=[self._new_lineage(initial,0)]
        self._remember(initial)
        # Resolve the initial record to the newly assigned starting lineage.
        self.best_origin={"type":"initial","lineage_id":self.parents[0].lineage_id,
                          "operator":None,"intensity":None}
        if self.best_records:
            self.best_records[0].update(self.best_origin)
            self.events[0].update(self.best_origin)
        self._save_best()
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
        presenter=getattr(self.problem,"progress_display",None)
        initial_display=str(presenter(self.best.state)) if callable(presenter) else f"initial_best={previous_best:.12f}"
        print(f"START generations={cfg.iterations} {initial_display} "
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
                explorer_proposals=[]
                for lineage in self.parents:
                    parent=lineage.candidate
                    improvements=[]
                    alternate=[]
                    for _ in range(cfg.children_per_parent):
                        if self.evaluations>=cfg.evaluation_budget:
                            break
                        k,intensity=self._sample_step(lineage)
                        child=self._mutate(parent,intensity,lineage=lineage)
                        self._step_feedback(lineage,k,parent,child)
                        if child is not None and child.score<parent.score:
                            improvements.append(child)
                        elif (child is not None and self._explorer_active(lineage)
                              and child.score<=min(lineage.explorer_baseline,
                                                   self.best.score+cfg.absolute_regression)
                              and self._distance(child,parent)>=cfg.min_distance):
                            alternate.append(child)
                    # A continuous, explicit chance to test a much longer jump,
                    # even after local progress has stopped. Archive the best
                    # objective independently of the chosen lineage.
                    jump_chance=cfg.jump_probability
                    if lineage.stagnation>=cfg.stagnation_jump_threshold:
                        jump_chance=min(0.5,2*jump_chance)
                    if self.evaluations<cfg.evaluation_budget and self.rng.random()<jump_chance:
                        self.step_stats["jump"]["calls"]+=1
                        trial,jump_operator=self._mutate(parent,cfg.jump_scale,
                                                         return_operator=True,
                                                         lineage=lineage,move_type="jump")
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
                            explorer_proposals.append((trial,lineage,jump_operator))
                            self.step_stats["jump"]["accepted"]+=1
                    child=min(improvements,key=lambda c:c.score) if improvements else parent
                    if (child is parent and alternate and self._explorer_active(lineage)
                            and self.rng.random()<cfg.explorer_uphill_probability):
                        child=self.rng.choice(alternate)
                        self.explorer_stats["uphill_steps"]+=1
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
                    self._write_genealogy(child,"selected_parent")
                    # A completed exploration trial may subsequently make a new
                    # improvement. Credit its originating move at most once,
                    # only when the active lineage actually crosses its
                    # original parent's baseline (not a global-best inference).
                    self._credit_late_explorer(lineage,child.score)
                    if lineage.explorer_until and step>=lineage.explorer_until:
                        self.explorer_stats["expired"]+=1
                        successful=(child.score<lineage.explorer_baseline)
                        if successful:
                            self.explorer_stats["improved_baseline"]+=1
                            lineage.explorer_credited=True
                            relative_gain=(lineage.explorer_baseline-child.score)/max(
                                1.,abs(lineage.explorer_baseline))
                            self._credit_operator(lineage.explorer_origin_operator,
                                                   min(1.,self.cfg.utility_gain_scale*relative_gain))
                        self.events.append({"generation":step,"event":"explorer_complete",
                            "success":successful,"birth_score":lineage.explorer_birth_score,
                            "final_score":child.score,"baseline":lineage.explorer_baseline,
                            "origin_operator":lineage.explorer_origin_operator,
                            "lineage_id":lineage.lineage_id})
                        lineage.explorer_until=0
                    next_parents.append(lineage)
                self.parents=next_parents
                # Spawn explorers outside the iteration to avoid mutating parents
                # while iterating. Do not allow more than one spawn per generation.
                for proposal,ancestor,operator in sorted(explorer_proposals,
                                                          key=lambda pair:pair[0].score):
                    if self._spawn_explorer(proposal,ancestor,operator,cfg.jump_scale):
                        break
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
                    # Optional domain-formatted display: no geometry enters the core.
                    presenter=getattr(self.problem,"progress_display",None)
                    domain_text=str(presenter(self.best.state)) if callable(presenter) else ""
                    # Domain adapters may supply a single user-facing metric.
                    # Preserve generic objective logging for other problems.
                    metric_text=(domain_text if domain_text else
                                 f"best_objective={current_best:.12f} "
                                 f"delta_objective={max(0.,improvement):.12f}")
                    print(f"STEP {step}/{cfg.iterations} "
                          f"{metric_text} "
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
                    "operator_memory":self.operator_memory,
                    "operator_weights":self.weights,
                    "best_origin":self.best_origin,
                    "best_node_id":self.best.node_id,
                    "genealogy_file":"genealogy.jsonl",
                    "best_records":self.best_records,
                    "late_credit_events":self.late_credit_events,
                    "historical_stats":self.historical_stats,
                    "historical_archive_count":len(self.historical_archive),
                    "step_stats":self.step_stats,
                    "explorer_stats":self.explorer_stats,
                    "population_diversity":self._population_diversity()})
        return Result(deepcopy(self.best.state),self._objective(self.best.score),
                      self.evaluations,self.generation,self.history,self.events)
