"""Fit a tapered pendant sleeve using cross sections of its existing influence region."""
import json
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector


def section(points, triangles, height):
    starts, ends = points[triangles], points[np.roll(triangles,-1,axis=1)]
    cross = (starts[:,:,2]>height)!=(ends[:,:,2]>height)
    faces = cross.sum(1)==2
    a,b = starts[faces][cross[faces]],ends[faces][cross[faces]]
    hits=(a+(b-a)*((height-a[:,2])/(b[:,2]-a[:,2]))[:,None]).reshape(-1,2,3)
    lengths=np.linalg.norm(hits[:,0]-hits[:,1],axis=1)
    if not len(lengths) or lengths.sum()<1e-9:
        raise ValueError('Missing sleeve section at '+str(height))
    return np.average(hits.mean(1),weights=lengths,axis=0)


def simplify(curve,segments):
    keep=[0,len(curve)-1]
    while len(keep)<=segments:
        errors=np.zeros(len(curve))
        for a,b in zip(keep,keep[1:]):
            axis=curve[b]-curve[a];delta=curve[a:b+1]-curve[a]
            t=np.clip(delta@axis/np.dot(axis,axis),0,1)
            errors[a:b+1]=np.linalg.norm(delta-t[:,None]*axis,axis=1)
        # Keep enough length either side for a usable joint.
        for i in keep:errors[max(0,i-4):i+5]=0
        idx=int(np.argmax(errors))
        if errors[idx]<=0:break
        keep=sorted(keep+[idx])
    return curve[keep]


def fit(obj,rig):
    points=np.array([obj.matrix_world@v.co for v in obj.data.vertices])
    obj.data.calc_loop_triangles()
    faces=np.array([t.vertices[:] for t in obj.data.loop_triangles])
    groups=obj.vertex_groups
    guide={}
    for sign in [1,-1]:
        side='Left' if sign==1 else 'Right'
        names=['Sleeve.'+str(sign),'SleeveTip.'+str(sign)]
        root=rig.data.bones[names[0]]
        pivot=np.array(rig.matrix_world@root.head_local)
        old=np.zeros(len(points))
        for v in obj.data.vertices:
            old[v.index]=sum(x.weight for x in v.groups if groups[x.group].name in names)
        region=faces[(old[faces].max(1)>.05)&(points[faces,1].mean(1)*sign>0)]
        bottom=points[region,2].min()
        heights=np.linspace(pivot[2]-.075,bottom+.001,77)
        curve=np.vstack([pivot]+[section(points,region,z) for z in heights])
        knots=simplify(curve,4)
        chain=[names[0]]+['SleevePanel.'+str(sign)+'.'+str(k) for k in range(1,len(knots)-2)]+[names[-1]]
        bpy.context.view_layer.objects.active=rig;rig.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
        inv=rig.matrix_world.inverted()
        for k,n in enumerate(chain):
            bone=rig.data.edit_bones.get(n) or rig.data.edit_bones.new(n)
            bone.use_connect=False
            bone.parent=rig.data.edit_bones[chain[k-1] if k else 'DEF-'+side+' elbow']
            bone.head=inv@Vector(knots[k]);bone.tail=inv@Vector(knots[k+1]);bone.use_connect=k>0
        bpy.ops.object.mode_set(mode='OBJECT')
        gg=[groups.get(n) or groups.new(name=n) for n in chain]
        lengths=np.linalg.norm(np.diff(knots,axis=0),axis=1);arc=np.r_[0,np.cumsum(lengths)]
        centers=(arc[:-1]+arc[1:])*.5
        for i in np.flatnonzero(old):
            # Reserve the original cuff/forearm weights; distribute only the free cloth's budget.
            pos=np.interp(points[i,2],knots[::-1,2],arc[::-1])
            blend=np.array([np.interp(pos,centers,row) for row in np.eye(len(chain))])
            for group in gg:group.remove([int(i)])
            for j in np.flatnonzero(blend):
                gg[j].add([int(i)],float(old[i]*blend[j]),'REPLACE')
        guide[side]=dict(bones=chain,knots=knots.tolist(),surface_curve=curve.tolist())
    return guide


if __name__=='__main__':
    out=Path(sys.argv[-1]).resolve()
    s=bpy.context.scene;r=s.objects['HumanArmature'];o=s.objects['layered-outfit']
    result=fit(o,r)
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(out))
    out.with_suffix('.json').write_text(json.dumps(result,indent=2))
