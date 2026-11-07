"""Run only inside Blender. Inventories are bounded structural checks, not QA scores."""
import hashlib
import json
from pathlib import Path
import runpy
import sys

import bpy
from mathutils import Vector
import numpy as np


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def array_hash(items, field, width, dtype=np.float32):
    data = np.empty(len(items) * width, dtype=dtype)
    items.foreach_get(field, data)
    return hashlib.sha256(data.tobytes()).hexdigest()


def inventory():
    objects, finite = {}, True
    for obj in sorted(bpy.context.scene.objects, key=lambda o: o.name):
        finite = finite and bool(np.isfinite(np.array(obj.matrix_world)).all())
        row = {'type': obj.type, 'parent': obj.parent.name if obj.parent else None,
               'transform': sha([list(r) for r in obj.matrix_world]),
               'bounds': [list(obj.matrix_world @ Vector(p)) for p in obj.bound_box],
               'modifiers': [{'name': m.name, 'type': m.type,
                              'object': getattr(getattr(m, 'object', None), 'name', None)} for m in obj.modifiers]}
        if obj.type == 'MESH':
            mesh = obj.data
            points = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
            mesh.vertices.foreach_get('co', points)
            finite = finite and bool(np.isfinite(points).all())
            row.update(vertices=len(mesh.vertices), polygons=len(mesh.polygons),
                       geometry=sha([hashlib.sha256(points.tobytes()).hexdigest(),
                                     array_hash(mesh.loops, 'vertex_index', 1, np.int32),
                                     array_hash(mesh.polygons, 'loop_total', 1, np.int32)]),
                       uv=sha([(u.name, array_hash(u.data, 'uv', 2)) for u in mesh.uv_layers]),
                       morphs=sha([(k.name, k.value, array_hash(k.data, 'co', 3))
                                   for k in mesh.shape_keys.key_blocks] if mesh.shape_keys else []),
                       shape_keys=[k.name for k in mesh.shape_keys.key_blocks] if mesh.shape_keys else [],
                       weights=sha([[g.name for g in obj.vertex_groups],
                                    [[(g.group, g.weight) for g in v.groups] for v in mesh.vertices]]),
                       materials=[s.material.name if s.material else None for s in obj.material_slots])
        elif obj.type == 'ARMATURE':
            row['rig'] = sha([(b.name, b.parent.name if b.parent else None,
                               list(b.head_local), list(b.tail_local), [list(r) for r in b.matrix_local])
                              for b in obj.data.bones])
            row['bone_count'] = len(obj.data.bones)
        objects[obj.name] = row
    scene = bpy.context.scene
    return {'blender_version': bpy.app.version_string, 'frame': scene.frame_current,
            'presentation': {'engine': scene.render.engine,
                             'resolution': [scene.render.resolution_x, scene.render.resolution_y,
                                            scene.render.resolution_percentage],
                             'camera': scene.camera.name if scene.camera else None,
                             'world_color': list(scene.world.color) if scene.world else None},
            'finite': finite, 'objects': objects,
            'actions': sorted(a.name for a in bpy.data.actions),
            'materials': [{'name': m.name, 'nodes': sorted(n.bl_idname for n in m.node_tree.nodes)
                           if m.use_nodes else []} for m in sorted(bpy.data.materials, key=lambda m: m.name)],
            'images': [{'name': im.name, 'size': list(im.size), 'packed': bool(im.packed_file)}
                       for im in sorted(bpy.data.images, key=lambda im: im.name)
                       if im.type not in ('RENDER_RESULT', 'COMPOSITING')]}


def import_assets(assets):
    if len(assets) == 1 and Path(assets[0]['path']).suffix.lower() == '.blend':
        bpy.ops.wm.open_mainfile(filepath=assets[0]['path'])
        return
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for index, asset in enumerate(assets):
        existing = set(bpy.data.objects)
        path = asset['path']
        if Path(path).suffix.lower() == '.obj':
            bpy.ops.wm.obj_import(filepath=path)
        else:
            bpy.ops.import_scene.gltf(filepath=path)
        prefix = asset.get('name', f'asset{index}')
        for obj in set(bpy.data.objects) - existing:
            obj.name = prefix + '__' + obj.name


def render_views(out, spec):
    scene = bpy.context.scene
    if spec is None:
        points = [obj.matrix_world @ Vector(p) for obj in scene.objects
                  if obj.type == 'MESH' and not obj.hide_render for p in obj.bound_box]
        if not points:
            raise ValueError('Scene contains no visible mesh')
        lo = Vector([min(p[i] for p in points) for i in range(3)])
        hi = Vector([max(p[i] for p in points) for i in range(3)])
        spec = {'center': list((lo + hi) / 2), 'span': max(max(hi - lo), .01) * 1.35,
                'label': 'Neutral geometry previews; not native-material validation'}
    write(out / 'views.json', spec)
    center, span = Vector(spec['center']), spec['span']
    previous_camera = scene.camera
    saved_render = {k: getattr(scene.render, k) for k in
                    ('engine', 'resolution_x', 'resolution_y', 'resolution_percentage',
                     'film_transparent', 'filepath')}
    saved_shading = {k: getattr(scene.display.shading, k) for k in
                     ('light', 'color_type', 'show_shadows', 'show_cavity', 'background_type')}
    saved_color = tuple(scene.display.shading.single_color)
    saved_world = tuple(scene.world.color)
    saved_format = scene.render.image_settings.file_format
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.color_type = 'SINGLE'
    scene.display.shading.single_color = (.65, .65, .65)
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.background_type = 'WORLD'
    scene.world.color = (.12, .12, .12)
    scene.render.resolution_x = scene.render.resolution_y = 384
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = False
    cam_data = bpy.data.cameras.new('LabPreviewCamera')
    cam = bpy.data.objects.new('LabPreviewCamera', cam_data)
    scene.collection.objects.link(cam)
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = span
    cam_data.clip_end = max(1000, span * 10)
    scene.camera = cam
    try:
        for name, direction in [('front', (0, -1, 0)), ('side', (1, 0, 0)),
                                ('back', (0, 1, 0)), ('quarter', (1, -1, .3))]:
            cam.location = center + Vector(direction).normalized() * span * 2
            cam.rotation_euler = (center - cam.location).to_track_quat('-Z', 'Y').to_euler()
            scene.render.filepath = str(out / (name + '.png'))
            bpy.ops.render.render(write_still=True)
    finally:
        scene.camera = previous_camera
        for key, value in saved_render.items():
            setattr(scene.render, key, value)
        for key, value in saved_shading.items():
            setattr(scene.display.shading, key, value)
        scene.display.shading.single_color = saved_color
        scene.world.color = saved_world
        scene.render.image_settings.file_format = saved_format
        bpy.data.objects.remove(cam, do_unlink=True)
        bpy.data.cameras.remove(cam_data)


def main():
    args = sys.argv[sys.argv.index('--') + 1:]
    request = json.loads(Path(args[0]).read_text())
    out = Path(request['out'])
    if '--readback' in args:
        bpy.ops.wm.open_mainfile(filepath=str(out / 'scene.blend'))
        bpy.context.view_layer.update()
        write(out / 'readback.json', inventory())
        if request['case'].get('geometry_checks'):
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from geometry_checks import evaluate
            write(out / 'geometry-readback.json', evaluate(request['case']['geometry_checks']))
        return
    if request['parent']:
        bpy.ops.wm.open_mainfile(filepath=request['parent'])
    else:
        import_assets(request['case']['assets'])
    bpy.context.view_layer.update()
    if (out / 'operation.py').exists():
        runpy.run_path(str(out / 'operation.py'), init_globals={'bpy': bpy, 'OUT': out,
                        'CASE': request['case']}, run_name='__lab_operation__')
    bpy.context.view_layer.update()
    if request['case'].get('geometry_checks'):
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from geometry_checks import evaluate
        write(out / 'geometry-checks.json', evaluate(request['case']['geometry_checks']))
    bpy.ops.file.pack_all()
    if not bpy.context.scene.world:
        bpy.context.scene.world = bpy.data.worlds.new('World')
    render_views(out, request['views'])
    bpy.context.view_layer.update()
    write(out / 'inventory.json', inventory())
    bpy.ops.wm.save_as_mainfile(filepath=str(out / 'scene.blend'))


if __name__ == '__main__':
    main()
