"""Blender -b baseline.blend --python-exit-code 1 -P refine_contacts.py -- settings.json NEW_DIR."""
from itertools import combinations
from pathlib import Path
import hashlib
import json
import sys
import time

import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from clearance import fit, surface, tree
from scalp_fit import fit_scalp


def audit(objects):
    trees = {}
    protected = {}
    topology = {}
    for name, obj in objects.items():
        if obj.hide_render or any(m.type == 'MASK' for m in obj.modifiers):
            raise ValueError(f'{name}: full unmasked mesh required')
        vertices, faces = surface(obj)
        trees[name] = tree(vertices, faces)
        protected[name] = hashlib.sha256(vertices.tobytes()).hexdigest()
        uv = [np.asarray([tuple(item.uv) for item in layer.data]).tobytes()
              for layer in obj.data.uv_layers]
        topology[name] = hashlib.sha256(faces.tobytes()+b''.join(uv)).hexdigest()
    pairs = {f'{a}/{b}': len(trees[a].overlap(trees[b])) for a,b in combinations(sorted(objects),2)}
    return dict(raw_pairs=pairs, world_vertices=protected, triangles_uv=topology)


def apply_local_fit(obj, objects, collider_name, fixed, p, t, q):
    """Require a real improvement on readback and protect previously clear neighbors."""
    original = tree(p,t)
    initial = len(fixed.overlap(original))
    ids = np.flatnonzero(np.linalg.norm(q-p,axis=1)>1e-10)
    if not len(ids):
        return initial, 0., 0., []
    lo = np.minimum(p.min(0),q.min(0))
    hi = np.maximum(p.max(0),q.max(0))
    guards = {}
    for name, other in objects.items():
        if name in (obj.name,collider_name):
            continue
        corners = np.array([other.matrix_world @ Vector(v) for v in other.bound_box])
        if np.any(corners.max(0)<lo) or np.any(corners.min(0)>hi):
            continue
        other_tree = tree(*surface(other))
        if not original.overlap(other_tree):
            guards[name] = other_tree
    inverse = obj.matrix_world.inverted()
    local = [obj.data.vertices[int(i)].co.copy() for i in ids]
    rejected = []
    for fraction in (1., .5, .25):
        for i in ids:
            obj.data.vertices[int(i)].co = inverse @ Vector(p[i]+fraction*(q[i]-p[i]))
        obj.data.update()
        actual, _ = surface(obj)
        candidate = tree(actual,t)
        pairs = len(fixed.overlap(candidate))
        conflicts = [name for name,other in guards.items() if candidate.overlap(other)]
        if pairs < initial and not conflicts:
            return pairs, float(np.linalg.norm(actual-p,axis=1).max()), fraction, rejected
        rejected.append(dict(fraction=fraction, pairs=pairs, new_crossings=conflicts))
    for i,co in zip(ids,local):
        obj.data.vertices[int(i)].co = co
    obj.data.update()
    return initial, 0., 0., rejected


def fit_group(obj, name, p, t, fixed, gap, budget, iterations, mobility):
    group = obj.vertex_groups.get(name)
    if group is None:
        raise ValueError(f"Missing repair vertex group {name!r} on {obj.name}")
    weights = np.zeros(len(p))
    for v in obj.data.vertices:
        for entry in v.groups:
            if entry.group == group.index:
                weights[v.index] = entry.weight
                break
    if mobility is not None:
        weights *= mobility
    # A UV split can duplicate a physical vertex. Respect the most restrictive lock.
    _, shared = np.unique(np.round(p, 7), axis=0, return_inverse=True)
    welded = np.ones(shared.max()+1)
    np.minimum.at(welded, shared, weights)
    weights = welded[shared]
    incident = t[np.any(weights[t] > 0, axis=1)]
    if not len(incident):
        raise ValueError(f"Empty repair region {name!r} on {obj.name}")
    ids, local = np.unique(incident, return_inverse=True)
    result = p.copy()
    result[ids], history = fit(p[ids], local.reshape(incident.shape), fixed, gap,
                               budget, iterations, weights[ids])
    return result, history


def meshes():
    return {o.name:o for o in bpy.context.scene.objects if o.type=='MESH'}


def main():
    settings, destination = map(Path,sys.argv[sys.argv.index('--')+1:])
    config=json.loads(settings.read_text())
    out=destination.resolve()
    out.mkdir(parents=True,exist_ok=False)
    objects=meshes()
    protected={config['head'],config['body']}
    def movable(name):
        if name in protected:
            raise ValueError(f'Cannot move protected mesh {name}')
        return objects[name]

    report={'before':audit(objects),'clearance':[]}
    if 'scalp' in config:
        spec=dict(config['scalp'],head=config['head'],body=config['body'])
        obj=movable(spec['hair'])
        scalp=fit_scalp(spec)
        obj.matrix_world=(Matrix.Translation(Vector(scalp['world_translation']))
                          @ Matrix.Scale(scalp['world_scale'],4) @ obj.matrix_world)
        report['scalp']=scalp
    for name,spec in config.get('placements',{}).items():
        obj=movable(name)
        p,_=surface(obj)
        mid=(p.max(0)+p.min(0))/2
        k=spec['height']/np.ptp(p[:,2])
        obj.matrix_world=(Matrix.Translation(Vector(spec['center'])) @ Matrix.Scale(k,4)
                          @ Matrix.Translation(-Vector(mid)) @ obj.matrix_world)
    bpy.context.view_layer.update()
    for step in config.get('clearance',[]):
        collider, faces=surface(objects[step['collider']])
        fixed=tree(collider,faces)
        height=np.ptp(collider[:,2])
        for name in step['parts']:
            if name==step['collider']:
                raise ValueError('A part cannot be its own contact reference')
            obj=movable(name)
            p,t=surface(obj)
            started=time.monotonic()
            mobility=None
            if 'height_fade' in step:
                low,high=step['height_fade']
                if not 0<=low<high<=1:
                    raise ValueError('height_fade needs two increasing relative heights')
                z=(p[:,2]-collider[:,2].min())/height
                a=np.clip((z-low)/(high-low),0,1)
                mobility=a*a*(3-2*a)
            args = (p, t, fixed, step['clearance']*height, step['max_offset']*height,
                    step['iterations'], mobility)
            if 'vertex_group' in step:
                q, history = fit_group(obj, step['vertex_group'], *args)
            else:
                q, history = fit(*args)
            pairs,offset,fraction,rejected=apply_local_fit(obj,objects,step['collider'],fixed,p,t,q)
            report['clearance'].append(dict(part=name,collider=step['collider'],history=history,
                                             vertex_group=step.get('vertex_group'),
                                             applied_pairs=pairs,seconds=time.monotonic()-started,
                                             max_offset=offset,applied_fraction=fraction,
                                             rejected_trials=rejected))
    bpy.ops.file.pack_all()
    path=str(out/'assembly.blend')
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    report['after']=audit(meshes())
    for name in protected:
        if report['before']['world_vertices'][name]!=report['after']['world_vertices'][name]:
            raise ValueError(f'Protected mesh changed: {name}')
    if report['before']['triangles_uv']!=report['after']['triangles_uv']:
        raise ValueError('Mesh topology or UV changed')
    (out/'contact-report.json').write_text(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
