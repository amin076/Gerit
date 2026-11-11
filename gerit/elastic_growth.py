"""Elastic all-square coordinate and angle relaxation for growing N -> N+1.

This is a separate, explicitly experimental solver. It never changes the
existing Gerit evolutionary engine, historical jumps, or answer archive.
Intermediate overlaps are permitted and penalised. Only independently
SAT-certified final poses are eligible for the best registry.

Dependencies: numpy, scipy. Angles are free in [-pi/4,+pi/4] modulo pi/2.
"""
from __future__ import annotations
import math

import numpy as np
from scipy.optimize import minimize
from scipy.spatial import cKDTree

from .geometry import Packing, Square, minimum_bounding_square, validate_packing


class ElasticEnergy:
    """Locally differentiable SAT penetration loss with analytic derivatives."""

    def __init__(self, n, side, angular_anchor, *, weight, angle_weight=2e-5):
        self.n=n
        self.side=side
        self.angular_anchor=angular_anchor.copy()
        self.weight=weight
        self.angle_weight=angle_weight

    def __call__(self,z):
        n=self.n
        coords=z[:2*n].reshape(n,2)
        angles=z[2*n:]
        co=np.cos(angles)
        si=np.sin(angles)
        extent=.5*(np.abs(co)+np.abs(si))
        extent_deriv=.5*(-np.sign(co)*si+np.sign(si)*co)
        gxy=np.zeros_like(coords)
        ga=np.zeros(n)
        cost=0.0

        # Only pairs within diagonal reach can intersect. Recomputed after
        # every move, so every square may move, not only a selected cluster.
        pairs=cKDTree(coords).query_pairs(1.5,output_type="ndarray")
        if len(pairs):
            i,j=pairs.T
            delta=coords[j]-coords[i]
            axes=np.stack((
                np.stack((co[i],si[i]),axis=1),
                np.stack((-si[i],co[i]),axis=1),
                np.stack((co[j],si[j]),axis=1),
                np.stack((-si[j],co[j]),axis=1),
            ),axis=1)
            proj=np.einsum("nd,nkd->nk",delta,axes)
            diff=angles[j]-angles[i]
            halfsum=.5+.5*(np.abs(np.cos(diff))+np.abs(np.sin(diff)))
            gaps=np.abs(proj)-halfsum[:,None]
            axis_choice=np.argmax(gaps,axis=1)
            active_gap=gaps[np.arange(len(i)),axis_choice]
            penetration=np.maximum(0.,-active_gap)
            cost+=self.weight*np.dot(penetration,penetration)
            selected=np.where(penetration>0)[0]
            if len(selected):
                ii=i[selected]
                jj=j[selected]
                which=axis_choice[selected]
                axis=axes[selected,which]
                sign=np.sign(proj[selected,which])
                pref=-2*self.weight*penetration[selected]
                dgap_dxy=sign[:,None]*axis
                np.add.at(gxy,ii,-pref[:,None]*dgap_dxy)
                np.add.at(gxy,jj,pref[:,None]*dgap_dxy)

                d=diff[selected]
                fprime=.5*(-np.sign(np.cos(d))*np.sin(d)
                          +np.sign(np.sin(d))*np.cos(d))
                rotation=np.einsum(
                    "nd,nd->n",delta[selected],
                    np.stack((-axis[:,1],axis[:,0]),axis=1))*sign
                owner_i=which<2
                dai=np.where(owner_i,rotation+fprime,fprime)
                daj=np.where(owner_i,-fprime,rotation-fprime)
                np.add.at(ga,ii,pref*dai)
                np.add.at(ga,jj,pref*daj)

        low=extent+2e-5
        high=self.side-extent-2e-5
        below=np.maximum(0.,low[:,None]-coords)
        above=np.maximum(0.,coords-high[:,None])
        cost+=2*self.weight*(np.sum(below**2)+np.sum(above**2))
        gxy+=4*self.weight*(-below+above)
        ga+=4*self.weight*extent_deriv*np.sum(below+above,axis=1)

        angle_delta=angles-self.angular_anchor
        cost+=self.angle_weight*np.dot(angle_delta,angle_delta)
        ga+=2*self.angle_weight*angle_delta
        return float(cost),np.concatenate((gxy.ravel(),ga))


def relax_once(poses, side_cap, *, iterations=400,
               penalty_schedule=(1,10,100,1000),angle_weight=2e-5):
    """Optimize all square centers and all angles, escalating collision penalty."""
    poses=np.asarray(poses,dtype=float).copy()
    n=len(poses)
    if poses.shape!=(n,3) or n<2:
        raise ValueError("Expected Nx3 square poses")
    if side_cap <= math.sqrt(n):
        raise ValueError("Side cap violates area lower bound")
    angles=poses[:,2].copy()
    z=np.concatenate((poses[:,:2].ravel(),angles))
    iterations_used=0
    for weight in penalty_schedule:
        energy=ElasticEnergy(n,side_cap,angles,weight=float(weight),
                             angle_weight=angle_weight)
        solution=minimize(
            energy,z,method="L-BFGS-B",jac=True,
            bounds=[(-1.,side_cap+1.)]*(2*n)+
                   [(-math.pi/4,math.pi/4)]*n,
            options={"maxiter":iterations,"ftol":1e-13,
                     "gtol":1e-8,"maxls":25})
        z=solution.x
        iterations_used+=solution.nit
    result=np.column_stack((z[:2*n].reshape(n,2),z[2*n:]))
    return result,float(energy(z)[0]),iterations_used


def initial_growth_pose(source:Packing, rng, target_side:float, *,
                        randomize_count:int=0):
    """Insert a unit square into the N-square founder; free ALL prior squares."""
    base=minimum_bounding_square(source.squares)
    poses=np.array([[s.x,s.y,s.angle] for s in base.squares],dtype=float)
    # Randomly choose a fresh square pose and retain every old square as
    # a movable variable. The target can be any valid number, not N=k²+1.
    new=np.array([[rng.uniform(1.,target_side-1.),
                   rng.uniform(1.,target_side-1.),
                   rng.choice([0.,math.pi/4,-math.pi/4])]],dtype=float)
    poses=np.vstack((poses,new))
    poses[:,:2]+=.05
    if randomize_count:
        ids=rng.choice(len(poses)-1,size=min(randomize_count,len(poses)-1),
                       replace=False)
        poses[ids,:2]+=rng.normal(0,.05,size=(len(ids),2))
    return poses


def certified_candidate(poses,cap):
    """Strict geometric endpoint check; independent interval SAT follows in runner."""
    items=tuple(Square(float(x),float(y),float(a)) for x,y,a in poses)
    p=minimum_bounding_square(items)
    if p.container_side>=cap-1e-10:
        return None
    return p if validate_packing(p,tolerance=0.).valid else None
