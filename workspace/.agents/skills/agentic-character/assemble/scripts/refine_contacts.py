"""Blender -b baseline.blend --python-exit-code 1 -P refine_contacts.py -- settings.json NEW_DIR."""
from itertools import combinations
from pathlib import Path
import hashlib
import json
import sys

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
            q,history=fit(p,t,fixed,step['clearance']*height,step['max_offset']*height,step['iterations'])
            if 'height_fade' in step:
                low,high=step['height_fade']
                if not 0<=low<high<=1:
                    raise ValueError('height_fade needs two increasing relative heights')
                z=(p[:,2]-collider[:,2].min())/height
                a=np.clip((z-low)/(high-low),0,1)
                q=p+(q-p)*(a*a*(3-2*a))[:,None]
            inverse=obj.matrix_world.inverted()
            for i in np.flatnonzero(np.linalg.norm(q-p,axis=1)>1e-10):
                obj.data.vertices[int(i)].co=inverse @ Vector(q[i])
            obj.data.update()
            report['clearance'].append(dict(part=name,collider=step['collider'],history=history,
                                             max_offset=float(np.max(np.linalg.norm(q-p,axis=1)))))
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
