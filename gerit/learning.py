"""Inheritable probabilistic mutation policy (contextual multiplicative weights).

The continuous search space is represented by distributions rather than a
probability for every possible displacement or angle. Each individual carries
policy genes. A parallel population-level policy learns from all trials.

Reward is determined by reducing the bounding side of the *child relative to
its own parent*, never by being SAT-valid alone or by beating unrelated parents.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import atan2, cos, exp, hypot, log, pi, sin, sqrt
import random
from .geometry import Packing, Square, minimum_bounding_square, square_vertices, validate_packing

ACTIONS = (
    "translate_x", "translate_y", "rotate", "single_pose",
    "pair_relative", "group_translate", "group_rotate",
    "group_contract", "boundary_inward", "neighbor_slide",
)
SIZE_BINS = ((0.006, 0.035), (0.035, 0.14), (0.14, 0.55))
ANGLE_BINS = ((0.002, 0.025), (0.025, 0.12), (0.12, 0.55))
SIGN_KEYS = ("x+", "x-", "y+", "y-", "cw", "ccw")


@dataclass(frozen=True)
class LearningSettings:
    epsilon_explore: float = 0.14
    global_blend: float = 0.40
    reward_logit_gain: float = 0.65
    failure_logit_cost: float = 0.035
    invalid_logit_cost: float = 0.045
    max_logit_abs: float = 5.0
    max_attempts_per_proposal: int = 55
    valid_improvement_epsilon: float = 1e-8
    # This fraction of improvement must exceed sampling noise to attain max reward
    full_reward_relative_improvement: float = 0.004


def _zero_policy() -> dict:
    return {
        "family": {ctx: {name: 0.0 for name in ACTIONS} for ctx in ("open", "dense")},
        "size": {name: [0.0, 0.0, 0.0] for name in ACTIONS},
        "sign": {name: 0.0 for name in SIGN_KEYS},
    }


def _clone_policy(state: dict) -> dict:
    return {
        "family": {ctx: dict(scores) for ctx, scores in state["family"].items()},
        "size": {name: list(values) for name, values in state["size"].items()},
        "sign": dict(state["sign"]),
    }


def _softmax(logits: list[float]) -> list[float]:
    z = max(logits)
    weights = [exp(min(30.0, x - z)) for x in logits]
    total = sum(weights)
    return [v / total for v in weights]


def _weighted_choice(rng: random.Random, values, weights):
    return rng.choices(values, weights=weights, k=1)[0]


def _clip(v: float, cap: float) -> float:
    return max(-cap, min(cap, v))


def _tight_bounds(pack: Packing) -> tuple[float, float, float, float]:
    v = [pos for s in pack.squares for pos in square_vertices(s)]
    return (min(x for x,y in v), max(x for x,y in v),
            min(y for x,y in v), max(y for x,y in v))


def _boundary_weights(pack: Packing) -> list[float]:
    x0,x1,y0,y1 = _tight_bounds(pack)
    weights=[]
    for sq in pack.squares:
        vs=square_vertices(sq)
        d=min(min(x for x,y in vs)-x0, x1-max(x for x,y in vs),
              min(y for x,y in vs)-y0, y1-max(y for x,y in vs))
        weights.append(0.1 + 1.0 / (0.02 + max(0.0, d)))
    return weights


def _nearest_neighbor(pack: Packing, idx: int) -> int:
    return min((j for j in range(len(pack.squares)) if j != idx),
               key=lambda j: hypot(pack.squares[idx].x - pack.squares[j].x,
                                   pack.squares[idx].y - pack.squares[j].y))


@dataclass
class LearningController:
    settings: LearningSettings = field(default_factory=LearningSettings)
    global_policy: dict = field(default_factory=_zero_policy)
    proposals: int = 0
    valid: int = 0
    improved_mutation: int = 0
    improved_final: int = 0
    compression_only_improvement: int = 0
    observations: dict = field(default_factory=lambda: {name: {"attempts": 0, "valid": 0, "improved": 0, "sum_side_gain": 0.0} for name in ACTIONS})

    def new_policy(self) -> dict:
        return _zero_policy()

    @staticmethod
    def context(pack: Packing) -> str:
        # Context is label-free and dimensionless; no combinatorial square IDs.
        return "dense" if len(pack.squares) / pack.container_side**2 >= 0.70 else "open"

    def probabilities(self, policy: dict, ctx: str) -> dict[str, float]:
        s = self.settings
        local = _softmax([policy["family"][ctx][name] for name in ACTIONS])
        glob = _softmax([self.global_policy["family"][ctx][name] for name in ACTIONS])
        n=len(ACTIONS)
        return {name: (1 - s.epsilon_explore)*((1-s.global_blend)*a+s.global_blend*b)+s.epsilon_explore/n for name,a,b in zip(ACTIONS,local,glob)}

    def _sample_sign(self, rng: random.Random, local: dict, plus: str, minus: str) -> str:
        logits=[(1-self.settings.global_blend)*local["sign"][name] + self.settings.global_blend*self.global_policy["sign"][name] for name in (plus,minus)]
        w=_softmax(logits)
        eps=self.settings.epsilon_explore
        return _weighted_choice(rng,(plus,minus),[(1-eps)*p+eps/2 for p in w])

    def _sample_size(self, rng:random.Random, local:dict,action:str) -> int:
        logits=[(1-self.settings.global_blend)*x+self.settings.global_blend*y for x,y in zip(local["size"][action],self.global_policy["size"][action])]
        w=_softmax(logits)
        eps=self.settings.epsilon_explore
        return _weighted_choice(rng,range(3),[(1-eps)*p+eps/3 for p in w])

    def choose_action(self, rng:random.Random,parent:Packing,policy:dict)->dict:
        ctx=self.context(parent)
        probs=self.probabilities(policy,ctx)
        action=_weighted_choice(rng,ACTIONS,[probs[name] for name in ACTIONS])
        size_idx=self._sample_size(rng,policy,action)
        signs={
            "x":self._sample_sign(rng,policy,"x+","x-"),
            "y":self._sample_sign(rng,policy,"y+","y-"),
            "rotation":self._sample_sign(rng,policy,"cw","ccw"),
        }
        return {"action":action,"context":ctx,"size_idx":size_idx,"signs":signs,
                "sampling_probability":probs[action]}

    def update(self, parent_policy: dict, proposal:dict, valid:bool,
               raw_gain:float, compression_gain:float, parent_side:float) -> tuple[dict,dict]:
        """Update shared memory and return an inheritable offspring copy.

        Direct mutation improvement has full credit; compression-only gains have
        small (0.25) credit since the mutation was a useful starting point but
        the local optimiser actually achieved the improvement.
        """
        s=self.settings
        self.proposals+=1
        if valid:self.valid+=1
        direct=valid and raw_gain > s.valid_improvement_epsilon
        final=valid and raw_gain + compression_gain > s.valid_improvement_epsilon
        if direct:self.improved_mutation+=1
        if final:self.improved_final+=1
        if final and not direct:self.compression_only_improvement+=1
        action=proposal["action"]
        obs=self.observations[action]
        obs["attempts"]+=1
        if valid:obs["valid"]+=1
        if final:
            obs["improved"]+=1
            obs["sum_side_gain"]+=raw_gain+compression_gain
        if direct:
            improvement = min(1.0, max(0.0,raw_gain/parent_side)/s.full_reward_relative_improvement)
            reward = 0.4 + 0.6*improvement
            update = s.reward_logit_gain*reward
        elif final:
            improvement = min(1.0, max(0.0,(raw_gain+compression_gain)/parent_side)/s.full_reward_relative_improvement)
            reward = 0.10 + 0.15*improvement
            update = s.reward_logit_gain*reward
        else:
            reward=0.0
            update= -s.failure_logit_cost if valid else -s.invalid_logit_cost
        # For unsuccessful births the child is not inherited, but global
        # statistics still learn which operators fail or collide.
        child_policy=_clone_policy(parent_policy)
        for store in (child_policy,self.global_policy):
            ctx=proposal["context"]
            store["family"][ctx][action]=_clip(store["family"][ctx][action]+update,s.max_logit_abs)
            idx=proposal["size_idx"]
            store["size"][action][idx]=_clip(store["size"][action][idx]+0.5*update,s.max_logit_abs)
            if direct or final:
                for sign in proposal["signs"].values():
                    store["sign"][sign]=_clip(store["sign"][sign]+0.25*update,s.max_logit_abs)
        return child_policy,{
            "valid":valid,"direct_improvement":bool(direct),"final_improvement":bool(final),
            "parent_side":parent_side,"raw_mutation_gain":raw_gain if valid else None,
            "compression_gain":compression_gain if valid else None,
            "final_side_gain":raw_gain+compression_gain if valid else None,
            "reward":reward,"logit_update":update,
        }

    def snapshot(self)->dict:
        return {"settings":asdict(self.settings),"proposals":self.proposals,
                "valid":self.valid,"improved_mutation":self.improved_mutation,
                "improved_final":self.improved_final,
                "compression_only_improvement":self.compression_only_improvement,
                "observations":self.observations,"global_policy":_clone_policy(self.global_policy),
                "family_probabilities":{ctx:self.probabilities(self.new_policy(),ctx) for ctx in ("open","dense")}}


def _propose_positions(parent:Packing,rng:random.Random,action:str,step:float,
                       angle_step:float,signs:dict) -> list[Square]:
    vals=list(parent.squares)
    n=len(vals)
    sx=1 if signs["x"]=="x+" else -1
    sy=1 if signs["y"]=="y+" else -1
    sr=1 if signs["rotation"]=="ccw" else -1
    role_weights=_boundary_weights(parent)
    index=_weighted_choice(rng,range(n),role_weights)
    old=vals[index]
    if action=="translate_x":
        vals[index]=Square(old.x+sx*step,old.y,old.angle)
    elif action=="translate_y":
        vals[index]=Square(old.x,old.y+sy*step,old.angle)
    elif action=="rotate":
        vals[index]=Square(old.x,old.y,old.angle+sr*angle_step)
    elif action=="single_pose":
        vals[index]=Square(old.x+sx*step/sqrt(2),old.y+sy*step/sqrt(2),old.angle+sr*angle_step)
    elif action=="boundary_inward":
        bx0,bx1,by0,by1=_tight_bounds(parent)
        cx,cy=(bx0+bx1)/2,(by0+by1)/2
        dx,dy=cx-old.x,cy-old.y
        d=hypot(dx,dy)
        if d<1e-8:dx,dy=1.,0.;d=1.
        vals[index]=Square(old.x+step*dx/d,old.y+step*dy/d,old.angle+sr*angle_step*0.2)
    elif action=="neighbor_slide":
        near=vals[_nearest_neighbor(parent,index)]
        ux,uy=old.x-near.x,old.y-near.y
        d=hypot(ux,uy)
        if d<1e-9: ux,uy,d=1.,0.,1.
        # Tangential slide along the neighbor rather than moving directly into it
        vals[index]=Square(old.x+sr*step*(-uy)/d,old.y+sr*step*ux/d,old.angle)
    elif action=="pair_relative":
        j=_nearest_neighbor(parent,index)
        other=vals[j]
        dx,dy=other.x-old.x,other.y-old.y
        d=hypot(dx,dy)
        if d<1e-9:dx,dy,d=1.,0.,1.
        # Together or apart: both directions remain possible.
        direction=1 if signs["x"]=="x+" else -1
        ux,uy=direction*step*dx/d,direction*step*dy/d
        vals[index]=Square(old.x+ux/2,old.y+uy/2,old.angle)
        vals[j]=Square(other.x-ux/2,other.y-uy/2,other.angle)
    else:
        count=min(n,rng.choice((2,3,4,5,min(n,7))))
        indices=sorted(rng.sample(range(n),count))
        cx=sum(vals[i].x for i in indices)/count
        cy=sum(vals[i].y for i in indices)/count
        if action=="group_translate":
            for idx in indices:
                o=vals[idx]
                vals[idx]=Square(o.x+sx*step,o.y+sy*step,o.angle)
        elif action=="group_rotate":
            c,ss=cos(sr*angle_step),sin(sr*angle_step)
            for idx in indices:
                o=vals[idx]
                dx,dy=o.x-cx,o.y-cy
                vals[idx]=Square(cx+dx*c-dy*ss,cy+dx*ss+dy*c,o.angle+sr*angle_step)
        elif action=="group_contract":
            factor=1-step if signs["x"]=="x+" else 1+step
            for idx in indices:
                o=vals[idx]
                vals[idx]=Square(cx+(o.x-cx)*factor,cy+(o.y-cy)*factor,o.angle)
        else:
            raise ValueError(f"Unknown action {action}")
    return vals


def propose_learned(parent:Packing,rng:random.Random,side_cap:float,
                    policy:dict,controller:LearningController) -> tuple[Packing|None,dict]:
    """Sample a probability distribution over continuous dx, dy and dtheta.

    Exactly one action family and one magnitude range is selected per birth;
    feasible trials only are accepted. The action is credited afterward by the
    caller using separately recorded raw and compression improvements.
    """
    choice=controller.choose_action(rng,parent,policy)
    action,idx=choice["action"],choice["size_idx"]
    low,high=SIZE_BINS[idx]
    alo,ahi=ANGLE_BINS[idx]
    for k in range(controller.settings.max_attempts_per_proposal):
        # Continuous log-uniform densities in each range, not a finite set of steps.
        step=exp(rng.uniform(log(low),log(high)))
        angle_step=exp(rng.uniform(log(alo),log(ahi)))
        try:
            vals=_propose_positions(parent,rng,action,step,angle_step,choice["signs"])
            p=minimum_bounding_square(tuple(vals))
        except (ValueError,OverflowError):
            continue
        if p.container_side>side_cap+1e-9:
            continue
        if not validate_packing(p,tolerance=0.0).valid:
            continue
        return p,{**choice,"valid":True,"step":step,"angle_step_radians":angle_step,
                  "normalized_step":step, "normalized_angle":angle_step/(pi/2),
                  "attempts_used":k+1,"rejected_reason":None}
    return None,{**choice,"valid":False,"step":None,"angle_step_radians":None,
                 "attempts_used":controller.settings.max_attempts_per_proposal,
                 "rejected_reason":"no_valid_move_in_selected_family"}