"""Blender skeleton FBX export followed by verification in a fresh Blender process."""
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import bpy
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parts():
    rigs = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE']
    if len(rigs) != 1:
        raise ValueError('Exactly one character armature required')
    return rigs[0], {o.name: o for o in bpy.context.scene.objects if o.type == 'MESH'}


def points(obj):
    obj = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = obj.to_mesh()
    result = [obj.matrix_world @ v.co for v in mesh.vertices]
    obj.to_mesh_clear()
    if not result or any(not math.isfinite(x) for p in result for x in p):
        raise ValueError('Empty or nonfinite surface')
    return result


def pose(rig, test):
    if rig.animation_data:
        rig.animation_data.action = None
    for bone in rig.pose.bones:
        bone.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    if test:
        bone = rig.pose.bones[test['bone']]
        rest_world = rig.matrix_world @ bone.bone.matrix_local
        head = rest_world.translation
        transform = Matrix.Translation(head) @ Matrix.Rotation(math.radians(test['degrees']), 4, test['axis']) @ Matrix.Translation(-head)
        bone.matrix = rig.matrix_world.inverted() @ transform @ rest_world
        bpy.context.view_layer.update()


def inventory(rig, meshes):
    deform = {b.name for b in rig.data.bones if b.use_deform}
    result = {'bones': {b.name: b.parent.name if b.parent else None for b in rig.data.bones}, 'meshes': {}}
    for name, obj in meshes.items():
        if not any(m.type=='ARMATURE' and m.object==rig for m in obj.modifiers):
            raise ValueError(f'Missing skin modifier: {name}')
        groups = {g.index: g.name for g in obj.vertex_groups}
        for vertex in obj.data.vertices:
            weights = [g.weight for g in vertex.groups if groups[g.group] in deform and g.weight>0]
            if not weights or len(weights)>4 or any(not math.isfinite(w) for w in weights) or abs(sum(weights)-1)>1e-4:
                raise ValueError(f'Invalid skin weights: {name}:{vertex.index}')
        result['meshes'][name] = {'triangles': sum(len(p.vertices)-2 for p in obj.data.polygons),
            'uv_layers': len(obj.data.uv_layers), 'materials': [m.name if m else None for m in obj.data.materials]}
    return result


def sample(meshes):
    result = {}
    for name, obj in meshes.items():
        ps = points(obj)
        step = max(1, len(ps)//4096)
        result[name] = {'points': [list(p) for p in ps[::step]],
                        'bounds': [[min(p[i] for p in ps) for i in range(3)],
                                   [max(p[i] for p in ps) for i in range(3)]]}
    return result


def verify(out):
    baseline = json.loads((out/'baseline.json').read_text())
    if sha(out/'character.fbx') != baseline['fbx_sha256']:
        raise ValueError('FBX changed before readback')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(out/'character.fbx'), use_anim=False)
    rig, meshes = parts()
    actual = inventory(rig, meshes)
    if actual != baseline['inventory']:
        raise ValueError('Reimported mesh/material/UV/triangle/skeleton inventory differs')
    comparisons = []
    tolerance = baseline['tolerance_scene_units']
    for i, test in enumerate(baseline['poses']):
        pose(rig, test)
        entries = {}
        for name, obj in meshes.items():
            ps = points(obj)
            tree = KDTree(len(ps))
            for j,p in enumerate(ps):
                tree.insert(p,j)
            tree.balance()
            expected = baseline['surfaces'][i][name]
            error = max(tree.find(Vector(p))[2] for p in expected['points'])
            bounds = [[min(p[k] for p in ps) for k in range(3)], [max(p[k] for p in ps) for k in range(3)]]
            bounds_error = max(abs(a-b) for row,other in zip(bounds,expected['bounds']) for a,b in zip(row,other))
            entries[name] = {'sample_nearest_max_scene_units': error, 'bounds_max_scene_units': bounds_error,
                             'pass': error <= tolerance and bounds_error <= tolerance}
        comparisons.append({'pose': test, 'meshes': entries})
    passed = all(m['pass'] for row in comparisons for m in row['meshes'].values())
    result = {'status': 'pass' if passed else 'fail', 'fbx_sha256': baseline['fbx_sha256'],
              'inventory': actual, 'comparisons': comparisons,
              'scope': 'Fresh-process skeleton, normalized skin, mesh/material-slot/UV counts and sampled rest/posed surfaces',
              'not_tested': ['Visual deformation quality', 'Intersections', 'Texture pixel/shader fidelity',
                             'Animation clip roundtrip', 'Engine behavior']}
    (out/'roundtrip.json').write_text(json.dumps(result, indent=2)+'\n')
    if not passed:
        raise ValueError('Posed FBX comparison failed; inspect roundtrip.json')


def export(config, out):
    assert sha(config['source']['path']) == config['source']['sha256'], 'Source changed'
    bpy.ops.wm.open_mainfile(filepath=str(Path(config['source']['path']).resolve()))
    rig, meshes = parts()
    if set(config['parts']) != set(meshes) or len(config['parts'])!=len(meshes):
        raise ValueError('Export must include every character mesh')
    if rig.data.pose_position != 'POSE' or any(max(abs(b.matrix_basis[i][j]-(1. if i==j else 0.)) for i in range(4) for j in range(4)) > 1e-6 for b in rig.pose.bones):
        raise ValueError('Input is not at rest; preserve the current pose and prepare a reviewed rest checkpoint before export')
    if rig.constraints or any(b.constraints for b in rig.pose.bones):
        raise ValueError('Bake constrained rigs into a reviewed deform-only checkpoint before export')
    if rig.animation_data and (rig.animation_data.action or rig.animation_data.nla_tracks):
        raise ValueError('This skeleton-only exporter requires a checkpoint without active animation/NLA; preserve original clips separately')
    tests = config.get('diagnostic_poses', [])
    if not tests:
        raise ValueError('Supply representative diagnostic poses to verify FBX skin behavior')
    for test in tests:
        if test.get('bone') not in rig.pose.bones or test.get('axis') not in {'X','Y','Z'} or not math.isfinite(test.get('degrees', float('nan'))) or abs(test['degrees']) < 1e-3:
            raise ValueError('Pose needs existing bone, world axis and nonzero finite degrees')
    tolerance = config.get('tolerance_scene_units', .0001)
    if not math.isfinite(tolerance) or not 0 < tolerance <= .01:
        raise ValueError('Use an explicit positive scene-unit tolerance <= 0.01')
    baseline = {'inventory': inventory(rig, meshes), 'poses': [None]+tests,
                'surfaces': [], 'tolerance_scene_units': tolerance}
    for test in baseline['poses']:
        pose(rig,test)
        baseline['surfaces'].append(sample(meshes))
    # A pose request that moves no sampled vertex is not a useful skin test.
    for index in range(1,len(baseline['surfaces'])):
        moved = max((Vector(a)-Vector(b)).length for name in meshes
                    for a,b in zip(baseline['surfaces'][0][name]['points'],baseline['surfaces'][index][name]['points']))
        if moved < 1e-6:
            raise ValueError('Diagnostic pose did not move the mesh')
    pose(rig,None)
    bpy.ops.object.select_all(action='DESELECT')
    rig.select_set(True)
    for obj in meshes.values():
        obj.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.export_scene.fbx(filepath=str(out/'character.fbx'), use_selection=True,
        object_types={'ARMATURE','MESH'}, add_leaf_bones=False, use_armature_deform_only=False,
        bake_anim=False, use_mesh_modifiers=False, axis_forward='-Z', axis_up='Y',
        apply_unit_scale=True, path_mode='COPY', embed_textures=True)
    baseline['fbx_sha256'] = sha(out/'character.fbx')
    (out/'baseline.json').write_text(json.dumps(baseline)+'\n')
    with (out/'readback.log').open('w') as log:
        result = subprocess.run([bpy.app.binary_path,'-b','--python-exit-code','1','--python',str(Path(__file__).resolve()),'--','verify',str(out)],
            stdout=log, stderr=subprocess.STDOUT, timeout=600)
    if result.returncode:
        raise RuntimeError('Fresh-process FBX verification failed; see readback.log')


def main():
    args = sys.argv[sys.argv.index('--')+1:]
    if args[0]=='verify':
        verify(Path(args[1]).resolve())
        return
    config_path, destination = args
    out = Path(destination).resolve()
    out.mkdir(parents=True, exist_ok=False)
    config = json.loads(Path(config_path).read_text())
    (out/'config.json').write_text(json.dumps(config, indent=2)+'\n')
    shutil.copy2(__file__,out/'export_fbx.py')
    export(config,out)


if __name__ == '__main__':
    main()
