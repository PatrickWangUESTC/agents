"""Fit hip and knee weight transitions using the fitted limb locations."""
import numpy as np


def smooth(t):
    t=np.clip(t,0,1)
    return t*t*(3-2*t)


def lower_body(weights, names, points, head):
    result=weights.copy()
    left,right=head('Left leg'),head('Right leg')
    origin=(left+right)/2
    up=head('Neck')-origin
    up/=np.linalg.norm(up)
    lateral=head('Left arm')-head('Right arm')
    lateral-=up*np.dot(up,lateral)
    lateral/=np.linalg.norm(lateral)
    y=np.sum((points-origin)*lateral,axis=1)
    z=np.sum((points-origin)*up,axis=1)
    length=np.mean([np.linalg.norm(head(s+' leg')-head(s+' knee')) for s in ('Left','Right')])
    # Thighs flex around the hip; blend the two sides only at the crotch.
    total=smooth((.30-z/length)/.8)
    width=np.maximum(.015*length,.45*length*smooth((z/length+.52)/.68))
    left_share=smooth(.5+y/(2*width))
    nonleg=np.ones(len(names),bool)
    for side in ('Left','Right'):
        for part in ('leg','knee','ankle','toe'):
            nonleg[names.index('DEF-'+side+' '+part)]=False
    orig_leg=weights[:,~nonleg].sum(1)
    # Preserve attached upper limbs and the original ankle/foot.
    arm=[i for i,n in enumerate(names) if n.endswith((' arm',' elbow',' wrist','_L','_R'))]
    mix=(1-smooth(weights[:,arm].sum(1)/.12))*smooth((z/length+1.85)/.4)
    modeled=np.zeros_like(weights)
    torso=weights[:,nonleg].sum(1)
    modeled[:,nonleg]=weights[:,nonleg]/np.maximum(torso,1e-10)[:,None]*(1-total[:,None])
    modeled[torso<1e-10,names.index('DEF-Hips')]=1-total[torso<1e-10]
    for side,share in [('Left',left_share),('Right',1-left_share)]:
        knee=head(side+' knee')
        axis=head(side+' ankle')-head(side+' leg')
        axis/=np.linalg.norm(axis)
        shin=smooth(.5+np.sum((points-knee)*axis,axis=1)/(.64*length))
        modeled[:,names.index('DEF-'+side+' leg')]=total*share*(1-shin)
        modeled[:,names.index('DEF-'+side+' knee')]=total*share*shin
    active=(orig_leg>0)|(z<.35*length)
    return np.where(active[:,None],weights+(modeled-weights)*mix[:,None],result)
