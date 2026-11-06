"""Inspect a native generated GLB without remeshing or reducing its geometry.

blender --background --factory-startup --python-exit-code 1 --python inspect_blender.py -- SOURCE OUT --part body
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import bpy
from mathutils import Vector


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('out', type=Path)
    parser.add_argument('--part', required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    source, out = args.source.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(source))
    bpy.context.view_layer.update()
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    if not meshes:
        raise ValueError('Source contains no meshes')
    inventory = []
    for index, obj in enumerate(meshes):
        obj.name = f'{args.part}/{index:02d}'
        obj.data.calc_loop_triangles()
        inventory.append({'object': obj.name, 'vertices': len(obj.data.vertices),
            'triangles': len(obj.data.loop_triangles),
            'finite_coordinates': all(math.isfinite(c) for v in obj.data.vertices for c in v.co),
            'uv_layers': list(obj.data.uv_layers.keys()),
            'materials': [m.name if m else None for m in obj.data.materials],
            'shape_keys': list(obj.data.shape_keys.key_blocks.keys()) if obj.data.shape_keys else [],
            'modifiers': [m.type for m in obj.modifiers]})
    assert all(o['finite_coordinates'] and o['triangles'] for o in inventory)
    coords = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
    low = Vector([min(v[i] for v in coords) for i in range(3)])
    high = Vector([max(v[i] for v in coords) for i in range(3)])
    center, span = (low + high) / 2, max(high - low)
    assert span > 0
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.render.resolution_x = scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.color_type = 'SINGLE'
    scene.display.shading.single_color = (.42, .58, .72)
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = False
    scene.display.shading.background_type = 'VIEWPORT'
    scene.display.shading.background_color = (.045, .055, .075)
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    scene.camera = camera
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = span * 1.2
    camera.data.clip_end = max(1000, span * 100)
    for label, direction in {'front': (0, -1, 0), 'side': (1, 0, 0),
                             'back': (0, 1, 0), 'three-quarter': (1, -2, .35)}.items():
        camera.location = center + Vector(direction).normalized() * span * 4
        camera.rotation_euler = (center - camera.location).to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = str(out / (label + '.png'))
        bpy.ops.render.render(write_still=True)
    scene.render.filepath = str(out / 'three-quarter.png')
    bpy.ops.wm.save_as_mainfile(filepath=str(out / 'part.blend'))
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original_hash
    report = {'scope': 'Native GLB import, inventory and neutral geometry renders; no geometry edits',
        'part': args.part, 'source': str(source), 'source_sha256': original_hash,
        'blender': bpy.app.version_string, 'meshes': inventory,
        'bounds': [list(low), list(high)], 'triangle_budget': None,
        'armatures': sum(o.type == 'ARMATURE' for o in scene.objects),
        'checks': {'import': 'pass', 'finite_coordinates': 'pass', 'source_preserved': 'pass',
                   'reference_fidelity': 'unknown', 'assembly_fit': 'not_run',
                   'rig': 'not_run', 'animation': 'not_run', 'engine': 'not_run'}}
    (out / 'inspection.json').write_text(json.dumps(report, indent=2) + '\n')
    print('NATIVE_INSPECTED', args.part, sum(o['triangles'] for o in inventory))


if __name__ == '__main__':
    main()
