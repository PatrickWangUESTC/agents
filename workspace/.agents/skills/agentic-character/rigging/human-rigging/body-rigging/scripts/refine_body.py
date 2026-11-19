"""Refine the skin of a fitted HumanArmature in Blender, before assembly."""
from heapq import heappop, heappush
import json
from pathlib import Path

import numpy as np


def smooth(x):
    t = np.clip(x, 0, 1)
    return t*t*(3-2*t)


def segment(points, start, end):
    axis = end-start
    t = np.sum((points-start)*axis,axis=1) / (axis @ axis)
    return np.linalg.norm(points-start-np.clip(t, 0, 1)[:, None]*axis, axis=1)


def distances(graph, seeds):
    distance = np.full(len(graph), np.inf)
    queue = []
    for i in np.flatnonzero(seeds):
        distance[i] = 0
        heappush(queue, (0, i))
    while queue:
        d, i = heappop(queue)
        if d > distance[i]:
            continue
        for j, cost in graph[i]:
            if d+cost < distance[j]:
                distance[j] = d+cost
                heappush(queue, (distance[j], j))
    return distance


def refine_body(body, rig, *, repair_lower=False, isolate_fingertips=False):
    bones = list(rig.data.bones)
    names = [b.name for b in bones]
    template = Path(__file__).resolve().parents[2]/'assets/HumanArmature.json'
    parents = {b['name']: b['parent'] for b in json.loads(template.read_text())['bones']}
    if {b.name: b.parent.name if b.parent else None for b in bones} != parents:
        raise ValueError('Expected the fitted 58-bone HumanArmature hierarchy')
    if body.find_armature() != rig:
        raise ValueError('Body must already use its fitted armature')
    def head(n):
        return np.array(rig.matrix_world @ rig.data.bones['DEF-'+n].head_local)
    points = np.array([body.matrix_world @ v.co for v in body.data.vertices])
    hips = head('Hips')
    shoulders = np.array([head(s+' arm') for s in ('Left','Right')])
    half_span = np.linalg.norm(shoulders[0]-shoulders[1])/2
    lateral = (shoulders[0]-shoulders[1])/(2*half_span)
    up = head('Neck')-hips
    up -= lateral*(up@lateral)
    up /= np.linalg.norm(up)
    # Coordinates in half shoulder spans. Only the graph copy welds UV seams.
    q, inv = np.unique(np.round((points-hips)/half_span,5),axis=0,return_inverse=True)
    inv = inv.ravel()
    edges = inv[np.array([e.vertices[:] for e in body.data.edges])]
    graph = [[] for _ in q]
    for i,j in np.unique(np.sort(edges,axis=1),axis=0):
        if i != j:
            cost = np.linalg.norm(q[i]-q[j])
            graph[i].append((j,cost))
            graph[j].append((i,cost))
    weights = np.zeros((len(points),len(names)))
    for v in body.data.vertices:
        for item in v.groups:
            name = body.vertex_groups[item.group].name
            if name in names:
                weights[v.index,names.index(name)] = item.weight
    if np.any(weights.sum(axis=1)<1e-6):
        raise ValueError('Missing initial body weights')
    weights /= weights.sum(axis=1)[:,None]
    result = weights.copy()
    y = np.sum((q-(shoulders.mean(axis=0)-hips)/half_span)*lateral,axis=1)
    z = np.sum(q*up,axis=1)
    height = (shoulders.mean(axis=0)-hips)@up/half_span
    core = (abs(y)<.58) | ((abs(y)<1.06)&(z<height-.92)) | ((z<-.65)&(abs(y)<1.22))
    core_dist = distances(graph,core)
    for sign,side,end in ((1,'Left','_L'),(-1,'Right','_R')):
        s,e,w = [(head(side+' '+k)-hips)/half_span for k in ('arm','elbow','wrist')]
        arm_dist = np.minimum(segment(q,s,e),segment(q,e,w))
        hand = [j for j,n in enumerate(names) if n.endswith(end) or n=='DEF-'+side+' wrist']
        arm_names = ['DEF-'+side+' arm','DEF-'+side+' elbow']
        arm = [names.index(n) for n in arm_names]
        ids = arm+hand
        seeds = (sign*y>1.22)&(arm_dist<.56)
        if not seeds.any() or not core.any():
            raise ValueError('Check the arm fit and rest pose before refining '+side)
        d = distances(graph,seeds)
        both = np.isfinite(d)&np.isfinite(core_dist)
        share = weights[:,ids].sum(1)
        share[np.isfinite(d)[inv]&~np.isfinite(core_dist)[inv]] = 1
        share[np.isfinite(core_dist)[inv]&~np.isfinite(d)[inv]] = 0
        reached = both[inv]
        at = inv[reached]
        share[reached] = smooth(.5+(core_dist[at]-d[at])/1.2)
        share[(sign*y[inv]<=0)|core[inv]] = 0
        # The hand can extend beyond the forearm axis. Keep its finger partition.
        fore = smooth(.5+np.sum((q-e)*(w-s)/np.linalg.norm(w-s),axis=1)/.85)[inv]
        hand_share = weights[:,hand].sum(axis=1)
        result[:,ids] = 0
        result[:,hand] = weights[:,hand]*share[:,None]
        result[:,arm[0]] = share*(1-hand_share)*(1-fore)
        result[:,arm[1]] = share*(1-hand_share)*fore
    limb = [j for j,n in enumerate(names) if n.endswith(('_L','_R',' arm',' elbow',' wrist'))]
    trunk = [j for j in range(len(names)) if j not in limb]
    available = np.clip(1-result[:,limb].sum(1),0,1)
    total = weights[:,trunk].sum(1)
    result[:,trunk] = weights[:,trunk]*np.divide(available,total,out=np.zeros_like(total),where=total>1e-8)[:,None]
    missing = (total<=1e-8)&(available>0)
    for i in np.flatnonzero(missing):
        spine = min(('Hips','Spine','Chest','Upper Chest','Neck'),key=lambda n: np.linalg.norm(points[i]-head(n)))
        result[i,names.index('DEF-'+spine)] = available[i]
    if repair_lower:
        from lower_body import lower_body
        result = lower_body(result,names,points,head)
    if isolate_fingertips:
        for side in ('L','R'):
            digits = ('Thumb','IndexFinger','MiddleFinger','RingFinger','LittleFinger')
            distances_to_tip = []
            lengths = []
            columns = []
            for digit in digits:
                prefix = 'DEF-'+digit
                first = rig.data.bones[prefix+'1_'+side]
                last = rig.data.bones[prefix+('2' if digit=='Thumb' else '3')+'_'+side]
                tip = np.array(rig.matrix_world @ last.tail_local)
                base = np.array(rig.matrix_world @ first.head_local)
                gap = np.linalg.norm(q-(tip-hips)/half_span,axis=1)
                distances_to_tip.append(distances(graph,gap<=gap.min()+1e-4)[inv])
                lengths.append(np.linalg.norm(tip-base)/half_span)
                columns.append([j for j,n in enumerate(names) if n.startswith(prefix) and n.endswith('_'+side)])
            d = np.stack(distances_to_tip,axis=1)
            closest = np.argmin(d,axis=1)
            for k,cols in enumerate(columns):
                region = closest==k
                trust = 1-smooth((d[:,k]/lengths[k]-.28)/.48)
                foreign = [j for m,ids in enumerate(columns) if m!=k for j in ids]
                take = trust*region
                retained = result[:,cols].sum(1)
                take[retained<1e-5] = 0
                freed = result[:,foreign].sum(1)*take
                result[:,foreign] *= 1-take[:,None]
                result[:,cols] *= (1+freed/np.maximum(retained,1e-8))[:,None]
    groups = [body.vertex_groups.get(n) for n in names]
    for i,row in enumerate(result):
        chosen = np.argsort(row)[-4:]
        total = row[chosen].sum()
        if not np.isfinite(total) or total<=0:
            raise ValueError('Invalid skin at vertex '+str(i))
        for j in np.flatnonzero(weights[i]):
            groups[j].remove([i])
        for j in chosen:
            if row[j]>1e-9:
                if groups[j] is None:
                    groups[j]=body.vertex_groups.new(name=names[j])
                groups[j].add([i],float(row[j]/total),'REPLACE')
    # Pose only the arm. Restore the original pose before the static save.
    import bpy
    from mathutils import Quaternion, Vector
    def evaluated():
        o = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
        return np.array([o.matrix_world @ v.co for v in o.data.vertices])
    sample = (abs(y[inv])<.95)&(z[inv]>0)&(z[inv]<height-1)
    bpy.context.view_layer.update()
    rest = evaluated()
    if len(rest)!=len(points) or not np.any(sample):
        raise ValueError('Run on the unmasked, fitted body before assembly')
    for side in ('Left','Right'):
        bone = rig.pose.bones['DEF-'+side+' arm']
        mode, basis = bone.rotation_mode, bone.matrix_basis.copy()
        try:
            axis = rig.matrix_world.to_3x3().inverted() @ Vector(np.cross(lateral,up))
            local = bone.bone.matrix_local.to_quaternion().inverted() @ axis
            bone.rotation_mode = 'QUATERNION'
            bone.rotation_quaternion = Quaternion(local, np.deg2rad(60))
            bpy.context.view_layer.update()
            displacement = np.linalg.norm(evaluated()-rest,axis=1)
            if (not np.isfinite(displacement).all() or displacement[sample].max()>half_span*1e-4
                    or displacement.max()<half_span*.1):
                raise ValueError('Check torso isolation and arm response on '+side)
        finally:
            bone.rotation_mode = mode
            bone.matrix_basis = basis
            bpy.context.view_layer.update()
    body['body_rigging_version']='surface-domains-v1'
