"""Rolling-window progress diagnosis for Gerit v4.

Preserves the v3 relative-credit learner, exact SAT validator, mutation operators,
and elite archive. Adds a distinct low-progress signal: brief positive but tiny
best-so-far changes must not indefinitely prevent structural exploration.
"""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass, asdict
from pathlib import Path
import json
import math

from .adaptive_v3 import (AdaptiveCreditController, StagnationController,
                          StagnationSettings, normalize_policy,
                          propose_micro, propose_reconfigure)

MODES = ('normal', 'precision', 'escape', 'diversify')


@dataclass(frozen=True)
class WindowSettings:
    window_generations: int = 80
    min_window_gain: float = 1e-4
    slow_precision_after: int = 1
    slow_escape_after: int = 20
    slow_diversify_after: int = 60

    def __post_init__(self):
        if self.window_generations < 2 or not math.isfinite(self.min_window_gain) or self.min_window_gain <= 0:
            raise ValueError('Window length must be >=2 and minimum gain finite and >0')
        if not 0 < self.slow_precision_after < self.slow_escape_after < self.slow_diversify_after:
            raise ValueError('Slow-progress thresholds must be strictly increasing')


class ProgressAwareStagnationController(StagnationController):
    """Mode is the stronger of v3 idle-gens and rolling low-progress evidence.

    `recent_best` contains monotonically nonincreasing best-side observations,
    one per completed generation, including the initial/imported last record.
    The rolling check activates only after a *full* window of observations.
    """
    def __init__(self, best_side, settings=None, window_settings=None):
        super().__init__(best_side, settings)
        self.window_settings = window_settings or WindowSettings()
        self.recent_best = deque([float(best_side)], maxlen=self.window_settings.window_generations+1)
        self.weak_progress_streak = 0
        self.window_gain = None
        self.history_source = 'fresh'

    def _observe_best(self, best_side):
        value=float(best_side)
        if not math.isfinite(value): raise ValueError('Nonfinite best side')
        if value > self.recent_best[-1]+1e-10:
            raise ValueError('Best-so-far must not increase')
        self.recent_best.append(value)
        if len(self.recent_best)==self.recent_best.maxlen:
            self.window_gain = max(0.,self.recent_best[0]-self.recent_best[-1])
            self.weak_progress_streak = self.weak_progress_streak+1 if self.window_gain < self.window_settings.min_window_gain else 0
        else:
            self.window_gain=None
            self.weak_progress_streak=0

    def restore_progress(self, progress_state=None, prior_generations_file=None):
        """Trust a saved v4 state, or reconstruct from adjacent v3 JSONL history.

        On legacy v3 input, all prior history can be reconstructed if the user
        still has generations.jsonl beside selected_population_final.json.
        Otherwise start a new window honestly, without invented observations.
        """
        if progress_state and progress_state.get('recent_best'):
            observed=[float(v) for v in progress_state['recent_best']]
            if len(observed) > self.recent_best.maxlen: observed=observed[-self.recent_best.maxlen:]
            if not math.isclose(observed[-1],self.recent_best[-1],rel_tol=0,abs_tol=1e-8):
                raise ValueError('Saved rolling best does not match imported best')
            self.recent_best=deque(observed,maxlen=self.recent_best.maxlen)
            self.weak_progress_streak=max(0,int(progress_state.get('weak_progress_streak',0)))
            self.window_gain=(max(0.,observed[0]-observed[-1]) if len(observed)==self.recent_best.maxlen else None)
            if self.window_gain is None:self.weak_progress_streak=0
            self.history_source='v4_stored_state'
            return self.history_source
        if prior_generations_file is not None and Path(prior_generations_file).is_file():
            with Path(prior_generations_file).open(encoding='utf-8') as f:
                values=[float(json.loads(line)['best_side']) for line in f if line.strip()]
            if values:
                if not math.isclose(values[-1],self.recent_best[-1],rel_tol=0,abs_tol=1e-8):
                    raise ValueError('Previous generations history does not match input population')
                self.recent_best=deque([values[0]],maxlen=self.recent_best.maxlen)
                self.window_gain=None;self.weak_progress_streak=0
                for value in values[1:]:self._observe_best(value)
                self.history_source='adjacent_generation_history'
                return self.history_source
        return self.history_source

    def mode(self, generation):
        old_mode=super().mode(generation)
        s=self.window_settings
        w=self.weak_progress_streak
        if w >= s.slow_diversify_after:win_mode='diversify'
        elif w >= s.slow_escape_after:win_mode='escape'
        elif w >= s.slow_precision_after:win_mode='precision'
        else:win_mode='normal'
        return max((old_mode,win_mode),key=MODES.index)

    def update(self,generation,best_side):
        self._observe_best(best_side)
        if self.reference_side-best_side>=self.settings.significant_gain:
            self.reference_side=best_side
            self.last_significant_generation=generation
        mode=self.mode(generation)
        if mode != self.previous_mode:
            self.transitions.append({'generation':generation,'from':self.previous_mode,'to':mode,
                                     'best_side':best_side,'rolling_window_gain':self.window_gain,
                                     'weak_progress_streak':self.weak_progress_streak})
            self.previous_mode=mode
        return mode

    def progress_snapshot(self):
        return {'settings':asdict(self.window_settings),'recent_best':list(self.recent_best),
                'weak_progress_streak':self.weak_progress_streak,
                'rolling_window_gain':self.window_gain,'history_source':self.history_source}

    def snapshot(self):
        state=super().snapshot()
        state['progress']=self.progress_snapshot()
        return state