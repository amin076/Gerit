"""Adaptive reward-v3 search: centered relative credit and bounded stagnation escape.

The v2 credit calculation is deliberately preserved as the diagnostic source.
Relative credit is assigned to chosen actions, sizes and directional pairs so
an overall negative reward cannot drive every action logit to -5.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from math import exp, log, pi
import random
from typing import Sequence

from . import learning as base
from .geometry import Square, Packing, minimum_bounding_square, validate_packing
from .reward_v2 import CreditController

STRUCTURAL = 'structural_relocate'
ACTIONS_V3 = (*base.ACTIONS, STRUCTURAL, 'micro_refine')
CONTEXTS = ('open', 'dense')
SIGN_PAIRS = (('x+', 'x-'), ('y+', 'y-'), ('cw', 'ccw'))


def _centered(values: Sequence[float], max_amplitude: float = 3.0) -> list[float]:
    """Keep relative evidence; never clip all category logits to same endpoint."""
    mean = sum(values) / len(values)
    vector = [float(v) - mean for v in values]
    amplitude = max(abs(v) for v in vector)
    if amplitude > max_amplitude:
        factor = max_amplitude / amplitude
        vector = [v * factor for v in vector]
    return vector


def _recenter(mapping: dict, keys: Sequence[str], cap: float) -> None:
    vals = _centered([mapping[k] for k in keys], cap)
    for k, value in zip(keys, vals):
        mapping[k] = value


def normalize_policy(policy: dict, cap: float = 3.0) -> dict:
    """Convert old v2 policy without discarding un-saturated relative genes.

    All-equal -5 family logits and all-equal +5 sign logits become neutral 0;
    genuine relative differences in size and family logits are preserved.
    """
    # Center existing v2 action logits BEFORE adding v3 actions; otherwise an
    # inherited all--5 vector would spuriously favor the new actions at zero.
    migrated_family = {}
    for ctx in CONTEXTS:
        prior = policy.get('family', {}).get(ctx, {})
        existing = [a for a in base.ACTIONS if a in prior]
        mean = sum(float(prior[a]) for a in existing)/len(existing) if existing else 0.0
        migrated_family[ctx] = {a: (float(prior[a])-mean if a in prior else 0.0)
                                for a in ACTIONS_V3}
    result = {
        'family': migrated_family,
        'size': {a: [float(v) for v in policy.get('size', {}).get(a, [0., 0., 0.])]
                 for a in ACTIONS_V3},
        'sign': {a: float(policy.get('sign', {}).get(a, 0.0)) for a in base.SIGN_KEYS},
    }
    for ctx in CONTEXTS:
        _recenter(result['family'][ctx], ACTIONS_V3, cap)
    for a in ACTIONS_V3:
        result['size'][a] = _centered(result['size'][a], cap)
    for pair in SIGN_PAIRS:
        _recenter(result['sign'], pair, cap)
    return result


@dataclass(frozen=True)
class AdaptiveLearningSettings:
    logit_cap: float = 3.0
    global_learning_rate: float = 3.0
    individual_learning_rate: float = 1.2
    baseline_ema: float = 0.025
    # Cap a single relative advantage update; important after archive restart.
    max_advantage: float = 0.08
    size_fraction: float = 0.55
    sign_fraction: float = 0.35


@dataclass
class AdaptiveCreditController(CreditController):
    adaptive_settings: AdaptiveLearningSettings = field(default_factory=AdaptiveLearningSettings)
    baseline_by_context: dict = field(default_factory=lambda: {ctx: 0.0 for ctx in CONTEXTS})
    action_advantage_totals: dict = field(default_factory=lambda: {a: 0.0 for a in ACTIONS_V3})
    action_advantage_counts: dict = field(default_factory=lambda: {a: 0 for a in ACTIONS_V3})

    def __post_init__(self):
        self.global_policy = normalize_policy(self.global_policy, self.adaptive_settings.logit_cap)

    def new_policy(self):
        return normalize_policy(super().new_policy(), self.adaptive_settings.logit_cap)

    def update(self, parent_policy, proposal, valid, raw_gain, compression_gain,
               parent_side, raw_checks, compression_checks, *, train=True,
               global_best_side: float | None = None):
        action = proposal['action']
        if action not in self.observations:
            self.observations[action] = {'attempts': 0, 'valid': 0,
                                         'improved': 0, 'sum_side_gain': 0.0}
        # Preserve the v2 accounting, costs, direct/compressor separation.
        _, feedback = super().update(parent_policy, proposal, valid, raw_gain,
                                     compression_gain, parent_side, raw_checks,
                                     compression_checks, train=False)
        parent = normalize_policy(parent_policy, self.adaptive_settings.logit_cap)
        if not train:
            feedback.update(relative_advantage=0.0, adaptive_training=False)
            return parent, feedback
        s = self.adaptive_settings
        # Rewards for beating one's own parent alone can favor uncompetitive
        # ancestors. Add small, explicit credit for a competitive child and
        # large credit for a genuine new global record.
        final_side = parent_side - raw_gain - compression_gain
        record_gain = max(0.0, (global_best_side - final_side)) if valid and global_best_side is not None else 0.0
        competitive = (0.02 * exp(-max(0., final_side-global_best_side)/0.02)
                       if valid and global_best_side is not None and
                       feedback['final_improvement'] else 0.)
        archive_bonus = 0.08 * min(1.0, record_gain/1e-4) if record_gain>1e-8 else 0.
        reward = (feedback['reward_direct'] + feedback['reward_compression']
                  + competitive + archive_bonus - feedback['cost_penalty'])
        feedback['reward_competitive'] = competitive
        feedback['reward_global_record'] = archive_bonus
        ctx = proposal['context']
        prior = self.baseline_by_context[ctx]
        advantage = max(-s.max_advantage, min(s.max_advantage, reward - prior))
        self.baseline_by_context[ctx] = (1 - s.baseline_ema) * prior + s.baseline_ema * reward
        self.action_advantage_totals[action] += advantage
        self.action_advantage_counts[action] += 1
        for store, rate in ((parent, s.individual_learning_rate),
                            (self.global_policy, s.global_learning_rate)):
            delta = rate * advantage
            fm = store['family'][ctx]
            # Zero-sum contrast across families, not cumulative all-negative drift.
            fm[action] += delta
            _recenter(fm, ACTIONS_V3, s.logit_cap)
            sizes = store['size'][action]
            sizes[proposal['size_idx']] += s.size_fraction * delta
            store['size'][action] = _centered(sizes, s.logit_cap)
            for pair in SIGN_PAIRS:
                chosen = next((v for v in pair if v in proposal['signs'].values()), None)
                if chosen is None:
                    continue
                store['sign'][chosen] += s.sign_fraction * delta
                _recenter(store['sign'], pair, s.logit_cap)
        feedback.update(relative_advantage=advantage, adaptive_training=True,
                        online_reward_baseline=self.baseline_by_context[ctx],
                        policy_logit_delta=s.individual_learning_rate*advantage)
        return parent, feedback

    def snapshot(self):
        result = super().snapshot()
        result['adaptive_settings'] = asdict(self.adaptive_settings)
        result['baseline_by_context'] = dict(self.baseline_by_context)
        result['action_advantage_totals'] = dict(self.action_advantage_totals)
        result['action_advantage_counts'] = dict(self.action_advantage_counts)
        return result


@dataclass(frozen=True)
class StagnationSettings:
    precision_after: int = 40
    escape_after: int = 80
    diversify_after: int = 120
    significant_gain: float = 1.0e-6

    def __post_init__(self):
        if not 0 < self.precision_after < self.escape_after < self.diversify_after:
            raise ValueError('Stagnation thresholds must be strictly increasing positive integers')
        if self.significant_gain <= 0:
            raise ValueError('Significant-gain threshold must be positive')


class StagnationController:
    """Phase depends on generations since meaningful global record improvement.

    Tiny numerical changes remain in the independent elite archive but do not
    reset the stagnation counter. A significant change returns to normal mode.
    """
    def __init__(self, best_side: float, settings: StagnationSettings | None = None):
        self.settings = settings or StagnationSettings()
        self.reference_side = best_side
        self.last_significant_generation = 0
        self.transitions = []
        self.previous_mode = 'normal'

    def mode(self, generation: int) -> str:
        idle = generation - self.last_significant_generation
        s = self.settings
        if idle >= s.diversify_after: return 'diversify'
        if idle >= s.escape_after: return 'escape'
        if idle >= s.precision_after: return 'precision'
        return 'normal'

    def update(self, generation: int, best_side: float) -> str:
        if self.reference_side - best_side >= self.settings.significant_gain:
            self.reference_side = best_side
            self.last_significant_generation = generation
        mode = self.mode(generation)
        if mode != self.previous_mode:
            self.transitions.append({'generation': generation,
                                     'from': self.previous_mode, 'to': mode,
                                     'best_side': best_side})
            self.previous_mode = mode
        return mode

    def snapshot(self):
        return {'settings': asdict(self.settings),
                'reference_side': self.reference_side,
                'last_significant_generation': self.last_significant_generation,
                'mode': self.previous_mode,
                'transitions': list(self.transitions)}


def _meta(action, pack, success, trials, idx=0):
    return {'action': action,
            'context': base.LearningController.context(pack),
            'size_idx': idx,
            'signs': {},
            'attempts_used': trials,
            'valid': success,
            'step': None, 'angle_step_radians': None,
            'rejected_reason': None if success else 'no_valid_reconfiguration'}


def propose_micro(parent: Packing, rng: random.Random, side_cap: float,
                  *, attempts: int = 28):
    """Tiny valid one-square moves with continuous logarithmic step sizes.

    These are *destination* checks, not validated continuous physical paths.
    """
    for attempt in range(1, attempts+1):
        squares = list(parent.squares)
        i = rng.randrange(len(squares))
        old = squares[i]
        # Seven orders smaller than the original mutation's minimum 0.006.
        step = exp(rng.uniform(log(1e-8), log(0.004)))
        angle = exp(rng.uniform(log(1e-8), log(0.003)))
        kind = rng.randrange(3)
        dx = rng.choice([-1,1])*step if kind != 1 else 0.
        dy = rng.choice([-1,1])*step if kind != 0 else 0.
        da = rng.choice([-1,1])*angle if kind == 2 else 0.
        squares[i] = Square(old.x+dx, old.y+dy, old.angle+da)
        candidate = minimum_bounding_square(tuple(squares))
        if candidate.container_side > side_cap+1e-10: continue
        if validate_packing(candidate, tolerance=0.0).valid:
            meta = _meta('micro_refine', parent, True, attempt)
            meta.update(step=step, angle_step_radians=angle,
                        signs={**({'x':'x+' if dx>0 else 'x-'} if dx else {}),
                               **({'y':'y+' if dy>0 else 'y-'} if dy else {}),
                               **({'rotation':'ccw' if da>0 else 'cw'} if da else {})})
            return candidate, meta
    return None, _meta('micro_refine', parent, False, attempts)


def propose_reconfigure(parent: Packing, rng: random.Random, side_cap: float,
                        *, attempts: int = 32):
    """Relocate 1–3 squares at once, leaving the remaining rigid geometry intact.

    The temporary arrangement is permitted to be disrupted; only strict-valid
    *final* geometry is returned to evolution. No known grid is injected.
    """
    n = len(parent.squares)
    for attempt in range(1, attempts+1):
        vals = list(parent.squares)
        moved = rng.sample(range(n), k=rng.choice((1, 1, 2, 3)))
        for i in moved:
            old = vals[i]
            # About 20% original angle, otherwise a lattice-friendly new angle.
            angle = (old.angle+rng.gauss(0, 0.18) if rng.random()<0.2
                     else rng.randrange(4)*pi/2+rng.gauss(0, 0.04))
            x = rng.uniform(.51, side_cap-.51)
            y = rng.uniform(.51, side_cap-.51)
            vals[i] = Square(x,y,angle)
        candidate = minimum_bounding_square(tuple(vals))
        if candidate.container_side > side_cap+1e-10: continue
        if validate_packing(candidate, tolerance=0.0).valid:
            meta = _meta(STRUCTURAL, parent, True, attempt, idx=2)
            meta['moved_squares'] = len(moved)
            return candidate, meta
    return None, _meta(STRUCTURAL, parent, False, attempts, idx=2)