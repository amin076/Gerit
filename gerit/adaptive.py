"""Feedback-controlled mutation for rigid-unit-square packings.

Only the child proposal operator is changed; selection and geometry are unchanged.
Move scale responds to packing density and empirical child-validity rate, while
occasional macro proposals preserve long-range exploration.
"""
from __future__ import annotations
import math
import random
from collections import deque
from dataclasses import dataclass, asdict
from .geometry import Square, Packing, minimum_bounding_square, validate_packing

@dataclass(frozen=True)
class AdaptiveSettings:
    base_translation_sigma: float = .48
    base_rotation_sigma: float = .70
    reference_density: float = 5.0 / 9.0
    target_valid_rate: float = .12
    feedback_window: int = 120
    min_scale: float = .10
    max_scale: float = 1.35
    macromove_probability: float = .10
    max_attempts_per_square: int = 85

class AdaptiveController:
    def __init__(self, settings: AdaptiveSettings = AdaptiveSettings()):
        self.settings = settings
        self.recent = deque(maxlen=settings.feedback_window)
        self.attempts = 0
        self.accepted = 0
        self.fail_collision = 0
        self.fail_container = 0
        self.fail_partial = 0
        self.proposed_macro = 0
        self.proposed_micro = 0

    def rate(self) -> float:
        return sum(self.recent) / len(self.recent) if self.recent else self.settings.target_valid_rate

    def scales(self, parent: Packing) -> tuple[float, float, float]:
        density = len(parent.squares) / (parent.container_side ** 2)
        density_factor = min(1.0, math.sqrt(self.settings.reference_density / max(density, 1e-12)))
        feedback_factor = math.sqrt(max(self.rate(), .003) / self.settings.target_valid_rate)
        scale = max(self.settings.min_scale, min(self.settings.max_scale, density_factor * feedback_factor))
        return self.settings.base_translation_sigma * scale, self.settings.base_rotation_sigma * scale, scale

    def record(self, success: bool, reason: str) -> None:
        self.recent.append(int(success))
        self.attempts += 1
        if success:
            self.accepted += 1
        elif reason == "container":
            self.fail_container += 1
        elif reason == "partial":
            self.fail_partial += 1
        else:
            self.fail_collision += 1

    def snapshot(self) -> dict:
        return {
            **asdict(self.settings),
            "recent_valid_rate": self.rate(),
            "attempts": self.attempts,
            "accepted": self.accepted,
            "failed_container": self.fail_container,
            "failed_partial": self.fail_partial,
            "failed_collision": self.fail_collision,
            "macro_attempts": self.proposed_macro,
            "micro_attempts": self.proposed_micro,
        }

def mutate_adaptive(parent: Packing, rng: random.Random, side_cap: float,
                    controller: AdaptiveController) -> tuple[Packing | None, dict]:
    """Make one child proposal, tracking its scale and rejection reason.

    This keeps the previous Gerit semantics: sequentially validated partial
    placements followed by a complete strict SAT validation; it is NOT a
    simultaneous-repacking method or a certified geometry proof.
    """
    n = len(parent.squares)
    sigma_xy, sigma_angle, scale = controller.scales(parent)
    macro = rng.random() < controller.settings.macromove_probability
    if macro:
        controller.proposed_macro += 1
    else:
        controller.proposed_micro += 1
    count = min(n, rng.choice((1, 1, 2, 2, 3, n)) if n >= 3 else 1)
    moving = set(rng.sample(range(n), count))
    values = list(parent.squares)
    meta = {
        "moved_indices": sorted(moving),
        "mode": "macro" if macro else "adaptive_local",
        "translation_sigma": sigma_xy,
        "rotation_sigma": sigma_angle,
        "scale": scale,
        "recent_valid_rate_before": controller.rate(),
    }
    for index in sorted(moving):
        old = values[index]
        found = False
        for attempt in range(controller.settings.max_attempts_per_square):
            if macro and attempt % 3 == 0:
                angle = rng.uniform(-math.pi / 4, math.pi / 4)
                x = rng.uniform(.5, side_cap - .5)
                y = rng.uniform(.5, side_cap - .5)
            else:
                angle = old.angle + rng.gauss(0, sigma_angle)
                x = old.x + rng.gauss(0, sigma_xy)
                y = old.y + rng.gauss(0, sigma_xy)
            trial = Square(x, y, angle)
            partial = tuple(values[j] for j in range(n) if j not in moving or j < index)
            candidate = minimum_bounding_square((*partial, trial))
            if validate_packing(candidate, tolerance=0.0).valid:
                values[index] = trial
                found = True
                break
        if not found:
            controller.record(False, "partial")
            meta["rejected_reason"] = "no_feasible_partial_move"
            return None, meta
    child = minimum_bounding_square(tuple(values))
    if not validate_packing(child, tolerance=0.0).valid:
        controller.record(False, "collision")
        meta["rejected_reason"] = "full_geometry_invalid"
        return None, meta
    if child.container_side > side_cap + 1e-9:
        controller.record(False, "container")
        meta["rejected_reason"] = "exceeds_side_cap"
        return None, meta
    controller.record(True, "valid")
    meta["rejected_reason"] = None
    meta["changed_indices"] = [i for i, (a, b) in enumerate(zip(parent.squares, child.squares)) if a != b]
    return child, meta
