"""Blender static-mesh binding with explicit bones and complete per-part policies."""
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
import bpy
from mathutils import Vector


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def world(obj, evaluated=False):
    target = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()) if evaluated else obj
    return [target.matrix_world @ v.co for v in target.data.vertices]


def validate(config, meshes):
    bindings = config['bindings']
    if set(bindings) != set(meshes):
        raise ValueError(f'Complete mesh inventory required; unlisted={set(meshes)-set(bindings)}, absent={set(bindings)-set(meshes)}')
    bones = config['bones']
    names = [b['name'] for b in bones]
    if not names or any(not isinstance(n,str) or not n.strip() for n in names) or len(set(names)) != len(names):
        raise ValueError('Bone names must be nonempty and unique')
    parent = {b['name']: b.get('parent') for b in bones}
    for bone in bones:
        coords = bone['head'] + bone['tail']
        if len(coords) != 6 or not all(math.isfinite(v) for v in coords) or sum((a-b)**2 for a,b in zip(bone['head'], bone['tail'])) < 1e-12:
            raise ValueError('Invalid bone endpoints')
        seen = {bone['name']}
        p = bone.get('parent')
        while p is not None:
            if p not in parent or p in seen:
                raise ValueError('Invalid bone hierarchy')
            seen.add(p)
            p = parent[p]
    deform = {b['name'] for b in bones if b.get('deform', True)}
    for name, policy in bindings.items():
        if policy['mode'] not in {'rigid', 'weights', 'automatic'}:
            raise ValueError(f'Unsupported binding mode: {name}')
        if policy['mode'] == 'rigid' and policy.get('bone') not in deform:
            raise ValueError(f'Rigid part needs an existing deform bone: {name}')
    return parent, deform


def execute(config, out):
    assert sha(config['source']['path']) == config['source']['sha256'], 'Source changed'
    bpy.ops.wm.open_mainfile(filepath=str(Path(config['source']['path']).resolve()))
    meshes = {o.name: o for o in bpy.context.scene.objects if o.type == 'MESH'}
    parent_map, deform = validate(config, meshes)
    if any(o.type == 'ARMATURE' for o in bpy.context.scene.objects) or any(o.modifiers or o.vertex_groups or o.data.shape_keys for o in meshes.values()):
        raise ValueError('Static unrigged input required; preserve existing rigs through a separate transfer workflow')
    if any(o.parent for o in meshes.values()):
        raise ValueError('Resolve existing mesh parenting before binding')
    reference = config.get('reference_skeleton')
    if reference:
        assert sha(reference['path']) == reference['sha256'], 'Skeleton template changed'
        with bpy.data.libraries.load(str(Path(reference['path']).resolve()), link=False) as (src, dst):
            if reference['object'] not in src.objects:
                raise ValueError('Reference armature object missing')
            dst.objects = [reference['object']]
        obj = dst.objects[0]
        if obj.type != 'ARMATURE':
            raise ValueError('Reference is not an armature')
        actual = {b.name: b.parent.name if b.parent else None for b in obj.data.bones}
        if actual != parent_map:
            raise ValueError('Bone names/parents differ from supplied reference')
        bpy.data.objects.remove(obj, do_unlink=True)
    baseline = {n: world(o) for n,o in meshes.items()}
    rig = bpy.data.objects.new('CharacterRig', bpy.data.armatures.new('CharacterSkeleton'))
    bpy.context.scene.collection.objects.link(rig)
    bpy.ops.object.select_all(action='DESELECT')
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    for entry in config['bones']:
        bone = rig.data.edit_bones.new(entry['name'])
        bone.head, bone.tail = entry['head'], entry['tail']
        bone.use_deform = entry.get('deform', True)
        if 'roll_axis' in entry:
            bone.align_roll(Vector(entry['roll_axis']))
    for name, parent in parent_map.items():
        if parent:
            rig.data.edit_bones[name].parent = rig.data.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    audits = {}
    for name, obj in meshes.items():
        policy = config['bindings'][name]
        matrix = obj.matrix_world.copy()
        if policy['mode'] == 'automatic':
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            rig.select_set(True)
            bpy.context.view_layer.objects.active = rig
            bpy.ops.object.parent_set(type='ARMATURE_AUTO')
            obj.matrix_world = matrix
        else:
            if policy['mode'] == 'rigid':
                obj.vertex_groups.new(name=policy['bone']).add(list(range(len(obj.data.vertices))), 1., 'REPLACE')
            else:
                assert sha(policy['path']) == policy['sha256'], 'Weight input changed'
                rows = json.loads(Path(policy['path']).read_text())
                if len(rows) != len(obj.data.vertices):
                    raise ValueError('Weights need one mapping per source vertex')
                for vertex, row in enumerate(rows):
                    if not row or len(row)>4 or not set(row)<=deform or any(not math.isfinite(v) or v<=0 for v in row.values()) or abs(sum(row.values())-1)>1e-5:
                        raise ValueError('Weights need 1-4 valid normalized deform influences')
                    for bone, weight in row.items():
                        group = obj.vertex_groups.get(bone) or obj.vertex_groups.new(name=bone)
                        group.add([vertex], weight, 'REPLACE')
            obj.parent = rig
            obj.matrix_world = matrix
            obj.modifiers.new('CharacterSkin', 'ARMATURE').object = rig
        # Heat weights are explicitly truncated/normalized; unweighted vertices fail.
        groups = {g.index: g.name for g in obj.vertex_groups}
        adjusted = 0
        for vertex in obj.data.vertices:
            weights = [(g.group, g.weight) for g in vertex.groups if groups[g.group] in deform and g.weight>0]
            if not weights or any(not math.isfinite(w) for _,w in weights):
                raise ValueError(f'Unweighted/invalid vertex: {name}:{vertex.index}')
            weights.sort(key=lambda pair: pair[1], reverse=True)
            kept = weights[:4]
            total = sum(w for _,w in kept)
            if len(weights)>4 or abs(total-1)>1e-6:
                adjusted += 1
            for group_index in [g.group for g in vertex.groups]:
                obj.vertex_groups[group_index].remove([vertex.index])
            for group, weight in kept:
                obj.vertex_groups[group].add([vertex.index], weight/total, 'REPLACE')
        bpy.context.view_layer.update()
        points = world(obj, evaluated=True)
        if len(points) != len(baseline[name]):
            raise ValueError('Rest topology changed')
        error = max((a-b).length for a,b in zip(points,baseline[name]))
        if error>1e-5:
            raise ValueError(f'Rest surface moved: {name}: {error}')
        audits[name] = {'mode': policy['mode'], 'vertices': len(points), 'rest_max_error_scene_units': error,
                        'weights_adjusted': adjusted, 'unweighted_vertices': 0}
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'rigged.blend'))
    report = {'status': 'produced', 'source': config['source'], 'blender_version': bpy.app.version_string,
              'bone_parents': parent_map, 'bindings': audits, 'reference_skeleton': reference,
              'output_sha256': sha(out/'rigged.blend'),
              'checks': {'complete_inventory': 'pass', 'weights': 'pass', 'rest_surface': 'pass',
                         'deformation_visual': 'not_run', 'posed_intersections': 'not_run'},
              'limitations': ['Explicit joint placement required; no semantic skeleton inference',
                              'Automatic heat binding may fail or deform poorly; no nearest-bone fallback',
                              'Rigid shoes do not bend at toes; test ankles and walking poses',
                              'No facial rig, cloth simulation, collision or engine acceptance']}
    (out/'rig-report.json').write_text(json.dumps(report, indent=2)+'\n')


def main():
    config_path, destination = sys.argv[sys.argv.index('--')+1:]
    out = Path(destination).resolve()
    out.mkdir(parents=True, exist_ok=False)
    config = json.loads(Path(config_path).read_text())
    (out/'config.json').write_text(json.dumps(config, indent=2)+'\n')
    shutil.copy2(__file__, out/'bind.py')
    execute(config, out)


if __name__ == '__main__':
    main()
