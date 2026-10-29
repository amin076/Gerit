# Gerit architecture — search independent of problem domain

## 1. Goal
Gerit is an extensible, budget-aware stochastic optimization algorithm.
A domain adapter defines states, constraints, objectives and mutation operators.
The engine must never depend on geometric coordinates, square rotation, or any domain-specific constraints.

## 2. Adapter protocol
- initial(rng): construct a starting solution
- feasible(state): test hard constraints
- evaluate(state): return a finite scalar objective
- distance(a,b): diversity measure (nonnegative, ideally zero only for equivalent states)
- encode(state): JSON-serializable representation for reliable best-solution checkpointing
- decode(payload): needed for solution restoration by consumers; not invoked by core v0.1
- operators[name](state,rng,intensity): propose new state (input is copied by engine)

Minimization is the default. maximize=True flips objective sign internally.
The initial solution must be feasible. Nonfinite objectives are discarded.
The domain controls validity; e.g. overlap detection belongs to a packing adapter, not to Gerit.

## 3. Evolution and selection
Each parent generates children_per_parent trial states.
Valid strict improvements replace that parent; otherwise it survives unchanged.
The global best is archived independently and never intentionally degraded.
Operator weights learn from improvements relative to the parent; exploration_floor
keeps nonwinning operators possible.

## 4. Adaptive branching
Every stagnation_window generations without significant_gain of global improvement,
the engine tries to seed max_parents diverse alternatives.
It first consults a bounded reservoir of earlier valid candidates, then performs
up to branch_seed_attempts additional trials.
Candidates must respect absolute_regression relative to the incumbent and min_distance.
Branching is best-effort; the event records requested/created counts. A branch_seed_shortfall
is a documented possibility, not silent success.
Competing parents evolve independently for competition_generations, then the best is
retained and the population shrinks to one. A checkpoint window provides a cooldown.

## 5. Compute budget
evaluation_budget caps candidate evaluations (including invalid proposals and branch
seeding attempts). iterations caps generations. Actual cost per evaluation is
problem-dependent, so equivalent evaluation budgets are not guaranteed equal runtime.

## 6. Persistence
best.json is atomically replaced immediately on a new global best.
status.json is periodically replaced and also written at shutdown.
run_summary.json records configuration, final objective and events.
Interruptions still leave best.json intact, but full-state deterministic resume
of RNG, parents, pool and competition state is NOT implemented yet.

## 7. Testing
The non-geometric quadratic example proves separation from square geometry.
Unit tests check finite best values, output persistence, budgets and seeded reproducibility.
More needed: adversarial constraints, nonfinite objective tests, zero-branch feasibility,
population diversity, prolonged stalls, budget exhaustion inside competitions,
resume fidelity and integration with a 12-square adapter.

## 8. Migration plan
1. Preserve existing scripts/run_single_lineage.py and prior results.
2. Implement a 12-square adapter with geometry validation, geometric mutation operators,
   objective container side, and packing serializer.
3. Compare old and generic search using identical initial packing and evaluation budget.
4. Add a resumable checkpoint containing RNG state, parents, policies, reservoir, history
   and pending branch competition, then validate deterministic continuation.
5. Only then migrate legacy experiment workflows.
