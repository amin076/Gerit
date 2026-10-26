"""Version 2 credit assignment for an inherited mutation policy.

Track independent rewards for mutation and local compression while penalizing
spent geometric checks. This module does not change any proposal families,
geometry, parent-selection quotas, or continuous sampling distributions.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from .learning import LearningController, LearningSettings, _clone_policy, _clip

@dataclass(frozen=True)
class CreditSettings:
    raw_target_fraction: float = 0.003
    compression_target_fraction: float = 0.003
    raw_gain_weight: float = 0.42
    compression_gain_weight: float = 0.075
    raw_cost_reference: float = 12.0
    compression_cost_reference: float = 45.0
    invalid_cost: float = 0.008
    stagnant_cost: float = 0.006
    max_step: float = 0.45
    sign_credit_fraction: float = 0.18
    size_credit_fraction: float = 0.45

@dataclass
class CreditController(LearningController):
    credit_settings: CreditSettings = field(default_factory=CreditSettings)
    cumulative_direct_reward: float = 0.0
    cumulative_compression_reward: float = 0.0
    cumulative_cost_penalty: float = 0.0
    cumulative_raw_checks: int = 0
    cumulative_compression_checks: int = 0
    positive_raw_gains: int = 0
    positive_final_gains: int = 0
    saved_events: list = field(default_factory=list)

    def update(self,parent_policy:dict, proposal:dict, valid:bool,
               raw_gain:float,compression_gain:float,parent_side:float,
               raw_checks:int,compression_checks:int, *,train:bool=True)->tuple[dict,dict]:
        if parent_side<=0 or raw_checks<0 or compression_checks<0:
            raise ValueError('Invalid cost or packing side')
        self.proposals+=1
        self.cumulative_raw_checks+=raw_checks
        self.cumulative_compression_checks+=compression_checks
        if valid:self.valid+=1
        epsilon=self.settings.valid_improvement_epsilon
        direct=bool(valid and raw_gain>epsilon)
        final_gain=raw_gain+compression_gain if valid else 0.0
        final=bool(valid and final_gain>epsilon)
        if direct:self.improved_mutation+=1;self.positive_raw_gains+=1
        if final:self.improved_final+=1;self.positive_final_gains+=1
        if final and not direct:self.compression_only_improvement+=1
        action=proposal['action']
        obs=self.observations[action]
        obs['attempts']+=1
        if valid:obs['valid']+=1
        if final:
            obs['improved']+=1
            obs['sum_side_gain']+=final_gain
        s=self.credit_settings
        # Raw gain attributable directly to the proposal, not its compressor.
        raw_strength=min(1.0, max(0.0,raw_gain)/(parent_side*s.raw_target_fraction)) if valid else 0.0
        # Compression is credited only for *final improvement not already
        # credited to mutation*. An intermediate worse raw child is not a win.
        extra_gain=max(0.0,final_gain)-max(0.0,raw_gain) if valid else 0.0
        comp_strength=min(1.0,extra_gain/(parent_side*s.compression_target_fraction))
        direct_reward=s.raw_gain_weight*raw_strength/(1.0+raw_checks/s.raw_cost_reference)
        compression_reward=(s.compression_gain_weight*comp_strength/
                            (1.0+(raw_checks+compression_checks)/s.compression_cost_reference))
        # Explicitly penalize invalid or stagnant proposals, relative to the
        # number of SAT calls consumed. Valid offspring without gain get no bonus.
        loss=0.0
        if not final:
            base=s.stagnant_cost if valid else s.invalid_cost
            loss=base*(1.0+(raw_checks+compression_checks)/55.0)
        update=_clip(direct_reward+compression_reward-loss,s.max_step)
        self.cumulative_direct_reward+=direct_reward
        self.cumulative_compression_reward+=compression_reward
        self.cumulative_cost_penalty+=loss
        policy=_clone_policy(parent_policy)
        if train:
            for store in (policy,self.global_policy):
                ctx=proposal['context']
                store['family'][ctx][action]=_clip(store['family'][ctx][action]+update,self.settings.max_logit_abs)
                k=proposal['size_idx']
                store['size'][action][k]=_clip(store['size'][action][k]+s.size_credit_fraction*update,self.settings.max_logit_abs)
                if final:
                    for sign in proposal['signs'].values():
                        store['sign'][sign]=_clip(store['sign'][sign]+s.sign_credit_fraction*update,self.settings.max_logit_abs)
        feedback={
            'train':train,'valid':bool(valid),'direct_improvement':direct,'final_improvement':final,
            'raw_mutation_gain':raw_gain if valid else None,
            'compression_gain':compression_gain if valid else None,
            'final_gain':final_gain if valid else None,
            'raw_geometry_checks':raw_checks,'compression_geometry_checks':compression_checks,
            'total_geometry_checks':raw_checks+compression_checks,
            'reward_direct':direct_reward,'reward_compression':compression_reward,
            'cost_penalty':loss,'policy_logit_delta':update if train else 0.0,
        }
        return policy,feedback

    def snapshot(self):
        r=super().snapshot()
        r.update(credit_settings=asdict(self.credit_settings),
                 cumulative_direct_reward=self.cumulative_direct_reward,
                 cumulative_compression_reward=self.cumulative_compression_reward,
                 cumulative_cost_penalty=self.cumulative_cost_penalty,
                 cumulative_raw_checks=self.cumulative_raw_checks,
                 cumulative_compression_checks=self.cumulative_compression_checks)
        return r