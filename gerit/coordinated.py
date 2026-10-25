"""Adaptive coordinated multi-square mutation for rigid unit-square packings."""
from __future__ import annotations
import math, random
from collections import deque
from dataclasses import dataclass, asdict
from .geometry import Square, Packing, minimum_bounding_square, validate_packing

@dataclass(frozen=True)
class CoordinatedSettings:
    base_group_translation_sigma: float = 0.36
    base_group_rotation_sigma: float = 0.42
    base_local_translation_sigma: float = 0.10
    base_local_rotation_sigma: float = 0.14
    base_contraction_sigma: float = 0.11
    reference_density: float = 5.0 / 9.0
    target_valid_rate: float = 0.10
    feedback_window: int = 120
    min_scale: float = 0.08
    max_scale: float = 1.25
    macro_probability: float = 0.10
    max_group_attempts: int = 100

class CoordinatedController:
    def __init__(self, settings: CoordinatedSettings = CoordinatedSettings()):
        self.settings=settings
        self.recent=deque(maxlen=settings.feedback_window)
        self.attempts=0
        self.accepted=0
        self.failed_collision=0
        self.failed_container=0
        self.failed_no_move=0
        self.macro_attempts=0
        self.micro_attempts=0

    def rate(self) -> float:
        return sum(self.recent)/len(self.recent) if self.recent else self.settings.target_valid_rate

    def scale(self, parent: Packing) -> float:
        density=len(parent.squares)/(parent.container_side**2)
        density_factor=min(1.0,math.sqrt(self.settings.reference_density/max(density,1e-12)))
        feedback_factor=math.sqrt(max(self.rate(),.0025)/self.settings.target_valid_rate)
        return max(self.settings.min_scale,min(self.settings.max_scale,density_factor*feedback_factor))

    def record(self, success: bool, reason: str) -> None:
        self.recent.append(1 if success else 0)
        self.attempts+=1
        if success: self.accepted+=1
        elif reason=="container": self.failed_container+=1
        elif reason=="no_move": self.failed_no_move+=1
        else: self.failed_collision+=1

    def snapshot(self) -> dict:
        return {**asdict(self.settings),
                "recent_valid_rate":self.rate(),
                "attempts":self.attempts,"accepted":self.accepted,
                "failed_container":self.failed_container,
                "failed_no_move":self.failed_no_move,
                "failed_collision":self.failed_collision,
                "macro_attempts":self.macro_attempts,
                "micro_attempts":self.micro_attempts}

def _centroid(squares: list[Square]) -> tuple[float,float]:
    return sum(s.x for s in squares)/len(squares),sum(s.y for s in squares)/len(squares)

def mutate_coordinated(parent: Packing, rng: random.Random, side_cap: float,
                       controller: CoordinatedController) -> tuple[Packing | None,dict]:
    """Simultaneously change 2-5 centers and angles, checking only complete endpoints."""
    n=len(parent.squares)
    scale=controller.scale(parent)
    macro=rng.random()<controller.settings.macro_probability
    if macro: controller.macro_attempts+=1
    else: controller.micro_attempts+=1
    if n>=5: count=rng.choice((2,2,3,3,4,5))
    elif n==4: count=rng.choice((2,2,3,4))
    else: count=min(n,rng.choice((2,3)))
    moving=sorted(rng.sample(range(n),count))
    group_sigma_xy=controller.settings.base_group_translation_sigma*scale
    group_sigma_angle=controller.settings.base_group_rotation_sigma*scale
    local_sigma_xy=controller.settings.base_local_translation_sigma*scale
    local_sigma_angle=controller.settings.base_local_rotation_sigma*scale
    contraction_sigma=controller.settings.base_contraction_sigma*scale
    old_group=[parent.squares[i] for i in moving]
    cx,cy=_centroid(old_group)
    parent_center=(parent.container_side/2,parent.container_side/2)
    meta={"moved_indices":moving,"mode":"macro_coordinated" if macro else "coordinated",
          "scale":scale,"group_translation_sigma":group_sigma_xy,
          "group_rotation_sigma":group_sigma_angle,
          "local_translation_sigma":local_sigma_xy,
          "local_rotation_sigma":local_sigma_angle,
          "contraction_sigma":contraction_sigma,
          "recent_valid_rate_before":controller.rate()}
    original=list(parent.squares)
    for attempt in range(controller.settings.max_group_attempts):
        if macro and attempt%4==0:
            dx=rng.uniform(-.5,.5)
            dy=rng.uniform(-.5,.5)
            dtheta=rng.uniform(-math.pi/6,math.pi/6)
            contraction=rng.uniform(-.12,.25)
        else:
            dx=rng.gauss(0.,group_sigma_xy)
            dy=rng.gauss(0.,group_sigma_xy)
            dtheta=rng.gauss(0.,group_sigma_angle)
            contraction=rng.gauss(0.,contraction_sigma)
        cos_t,sin_t=math.cos(dtheta),math.sin(dtheta)
        drift_x=(parent_center[0]-cx)*min(.22,max(-.22,contraction))
        drift_y=(parent_center[1]-cy)*min(.22,max(-.22,contraction))
        new_values=list(original)
        any_change=False
        for idx in moving:
            s=original[idx]
            rx,ry=s.x-cx,s.y-cy
            contract_factor=1.0-contraction
            rr_x=contract_factor*(rx*cos_t-ry*sin_t)
            rr_y=contract_factor*(rx*sin_t+ry*cos_t)
            nx=cx+rr_x+dx+drift_x+rng.gauss(0.,local_sigma_xy)
            ny=cy+rr_y+dy+drift_y+rng.gauss(0.,local_sigma_xy)
            na=s.angle+dtheta+rng.gauss(0.,local_sigma_angle)
            candidate=Square(nx,ny,na)
            new_values[idx]=candidate
            if candidate!=s: any_change=True
        if not any_change: continue
        child=minimum_bounding_square(tuple(new_values))
        if not validate_packing(child,tolerance=0.0).valid: continue
        if child.container_side>side_cap+1e-9: continue
        controller.record(True,"valid")
        meta["rejected_reason"]=None
        meta["changed_indices"]=[i for i,(a,b) in enumerate(zip(parent.squares,child.squares)) if a!=b]
        meta["group_attempts_used"]=attempt+1
        return child,meta
    controller.record(False,"collision")
    meta["rejected_reason"]="no_valid_coordinated_move"
    meta["group_attempts_used"]=controller.settings.max_group_attempts
    return None,meta
