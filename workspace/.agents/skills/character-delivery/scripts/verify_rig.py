"""Read native, GLB and FBX in clean scenes; compare actual posed geometry."""
import json, math, sys, hashlib
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree


def world(obj):
    obj = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = obj.to_mesh()
    values = np.empty(len(mesh.vertices) * 3, np.float32)
    mesh.vertices.foreach_get('co', values)
    mat = np.asarray(obj.matrix_world)
    result = np.einsum('ij,nj->ni', mat[:3,:3], values.reshape(-1,3)) + mat[:3,3]
    obj.to_mesh_clear()
    return result


def action_for(name):
    choices = [a for a in bpy.data.actions if name in a.name]
    if len(choices) != 1:
        raise ValueError(f'Ambiguous action {name}: {[a.name for a in choices]}')
    return choices[0]


def pose(rig, name, fraction):
    action = action_for(name)
    rig.animation_data_create()
    rig.animation_data.action = action
    # Imported FBX contains additional object curves; keep their evaluated transforms.
    start, end = action.frame_range
    frame = start + (end - start) * fraction
    bpy.context.scene.frame_set(math.floor(frame), subframe=frame-math.floor(frame))
    bpy.context.view_layer.update()


def snapshot(meshes):
    data = {}
    for obj in meshes:
        points = world(obj)
        assert np.isfinite(points).all()
        step = max(1, len(points)//2048)
        data[obj.name] = {'samples': points[::step].copy(), 'bounds': np.stack([points.min(0),points.max(0)]),
                          'triangles': sum(len(p.vertices)-2 for p in obj.data.polygons)}
    return data


def image(scene, setup, output):
    world_data = bpy.data.worlds.new('ReadbackWorld')
    world_data.use_nodes = True
    world_data.node_tree.nodes['Background'].inputs['Color'].default_value = (.22,.25,.3,1)
    world_data.node_tree.nodes['Background'].inputs['Strength'].default_value = .4
    scene.world = world_data
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.matrix_world = Matrix(setup['camera_matrix'])
    camera.data.type='ORTHO';camera.data.ortho_scale=setup['ortho_scale'];scene.camera=camera
    for light in setup['lights']:
        bpy.ops.object.light_add(type='AREA')
        obj=bpy.context.object;obj.matrix_world=Matrix(light['matrix'])
        obj.data.energy=light['energy'];obj.data.size=light['size']
    scene.render.engine='BLENDER_EEVEE_NEXT';scene.view_settings.view_transform='AgX'
    scene.render.film_transparent=True;scene.render.resolution_x=640;scene.render.resolution_y=720
    scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
    scene.render.filepath=str(output);bpy.ops.render.render(write_still=True)


def main():
    root=Path(sys.argv[sys.argv.index('--')+1]).resolve()
    report=json.loads((root/'rig-report.json').read_text())
    tests=[('Pose_Check',0.),('Pose_Check',.125),('Pose_Check',.625),('Pose_Check',.875),('Walk_InPlace',.25)]
    bpy.ops.wm.open_mainfile(filepath=str(root/'character-rigged.blend'))
    rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    meshes=[bpy.data.objects[n] for n in report['source_signatures']]
    names={b.name:b.parent.name if b.parent else None for b in rig.data.bones}
    setup={'camera_matrix':[list(v) for v in bpy.context.scene.camera.matrix_world],
           'ortho_scale':bpy.context.scene.camera.data.ortho_scale,
           'lights':[{'matrix':[list(v) for v in o.matrix_world],'energy':o.data.energy,'size':o.data.size}
                     for o in bpy.context.scene.objects if o.type=='LIGHT' and o.data.type=='AREA']}
    baseline={}
    for name,t in tests:
        pose(rig,name,t);baseline[(name,t)]=snapshot(meshes)
    results={}
    for extension in ['glb','fbx']:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        file=root/('character-rigged.'+extension)
        if extension=='glb':bpy.ops.import_scene.gltf(filepath=str(file))
        else:bpy.ops.import_scene.fbx(filepath=str(file),use_anim=True)
        rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']
        assert len(rigs)==1
        rig=rigs[0]
        # Blender's glTF importer creates an Icosphere custom bone widget. It is
        # an importer UI helper, not an exported character mesh.
        widgets={pb.custom_shape for pb in rig.pose.bones if pb.custom_shape}
        meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o not in widgets]
        assert {o.name for o in meshes}==set(report['source_signatures'])
        parent_map={b.name:b.parent.name if b.parent else None for b in rig.data.bones}
        result={'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'bones':len(parent_map),
                'names_and_parents_identical':parent_map==names,'actions':[a.name for a in bpy.data.actions],
                'importer_bone_widgets_excluded':[o.name for o in widgets],
                'weights':{},'posed_comparison':{}}
        for obj in meshes:
            totals=np.array([sum(g.weight for g in v.groups) for v in obj.data.vertices])
            result['weights'][obj.name]={'unweighted':int((totals<=1e-8).sum()),
                                         'max_sum_error':float(abs(totals-1).max()),
                                         'armature_modifier':any(m.type=='ARMATURE' and m.object==rig for m in obj.modifiers)}
        for name,t in tests:
            pose(rig,name,t)
            entries={}
            for obj in meshes:
                expected=baseline[(name,t)][obj.name]
                points=world(obj)
                tree=KDTree(len(points))
                for i,p in enumerate(points):tree.insert(Vector(p),i)
                tree.balance()
                errors=np.array([tree.find(Vector(p))[2] for p in expected['samples']])
                bounds=np.stack([points.min(0),points.max(0)])
                entries[obj.name]={'finite':bool(np.isfinite(points).all()),
                    'sample_count':len(errors),'sample_nearest_error_max_m':float(errors.max()),
                    'sample_nearest_error_mean_m':float(errors.mean()),
                    'bounds_error_max_m':float(abs(bounds-expected['bounds']).max()),
                    'triangles_match':sum(len(p.vertices)-2 for p in obj.data.polygons)==expected['triangles']}
            result['posed_comparison'][f'{name}:{t}']=entries
        pose(rig,'Pose_Check',.125)
        image(bpy.context.scene,setup,root/f'{extension}-readback-pose.png')
        result['pass']=(result['names_and_parents_identical'] and
            all(v['unweighted']==0 and v['max_sum_error']<1e-4 and v['armature_modifier'] for v in result['weights'].values()) and
            all(v['finite'] and v['triangles_match'] and v['sample_nearest_error_max_m']<.002 and v['bounds_error_max_m']<.002
                for views in result['posed_comparison'].values() for v in views.values()))
        results[extension]=result
        (root/'roundtrip.json').write_text(json.dumps({'scope':'Native vs clean GLB/FBX imports; five evaluated poses, ~2048 surface samples per part per pose; not collision or engine validation','results':results},indent=2)+'\n')
    assert all(r['pass'] for r in results.values()),'Read roundtrip.json for actual failures'
    print('RIG_ROUNDTRIP_PASS',[(k,v['bones']) for k,v in results.items()])


if __name__=='__main__':main()
