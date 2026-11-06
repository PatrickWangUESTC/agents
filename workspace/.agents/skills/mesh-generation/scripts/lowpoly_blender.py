"""Import a generated source, retain it, derive a budgeted GLB and render evidence.

blender --background --factory-startup --python lowpoly_blender.py -- SOURCE OUT --budget 5000
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Vector


def counts():
    objects = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    triangles = 0
    polygons = Counter()
    vertices = 0
    finite = True
    for obj in objects:
        obj.data.calc_loop_triangles()
        triangles += len(obj.data.loop_triangles)
        polygons.update(len(p.vertices) for p in obj.data.polygons)
        vertices += len(obj.data.vertices)
        finite = finite and all(math.isfinite(c) for v in obj.data.vertices for c in v.co)
    return {"mesh_objects": len(objects), "vertices": vertices, "triangles": triangles,
            "polygon_sizes": dict(polygons), "finite_coordinates": finite}


def bounds():
    coords = [o.matrix_world @ Vector(c) for o in bpy.context.scene.objects
              if o.type == 'MESH' for c in o.bound_box]
    lower = Vector([min(p[i] for p in coords) for i in range(3)])
    upper = Vector([max(p[i] for p in coords) for i in range(3)])
    return lower, upper


def main():
    p = argparse.ArgumentParser()
    p.add_argument("source", type=Path)
    p.add_argument("out", type=Path)
    p.add_argument("--budget", type=int, default=5000)
    p.add_argument("--merge-coincident", action='store_true',
                   help="Explicit geometry-only seam repair before decimation; original retained")
    p.add_argument("--voxel-resolution", type=int,
                   help="Optional explicit geometry reconstruction: voxels along largest dimension")
    args = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
    if args.budget < 100:
        raise ValueError("Budget must be at least 100 triangles")
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    source = args.source.resolve()
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    suffix = source.suffix.lower()
    if suffix in {'.glb', '.gltf'}:
        bpy.ops.import_scene.gltf(filepath=str(source))
    elif suffix == '.obj':
        bpy.ops.wm.obj_import(filepath=str(source))
    elif suffix == '.fbx':
        bpy.ops.import_scene.fbx(filepath=str(source))
    else:
        raise ValueError("Unsupported source; unpack or convert explicitly first")
    bpy.context.view_layer.update()
    before = counts()
    assert before['mesh_objects'] and before['vertices'] and before['finite_coordinates']
    original_bounds = [list(v) for v in bounds()]
    bpy.ops.wm.save_as_mainfile(filepath=str(out / 'source-import.blend'))
    voxel_report = []
    if args.voxel_resolution is not None:
        if not 100 <= args.voxel_resolution <= 800:
            raise ValueError("Voxel resolution must be between 100 and 800")
        low, high = bounds()
        for obj in [o for o in bpy.context.scene.objects if o.type == 'MESH']:
            bpy.context.view_layer.objects.active = obj
            obj.data.remesh_voxel_size = max(high - low) / args.voxel_resolution
            bpy.ops.object.voxel_remesh()
            voxel_report.append({'object': obj.name, 'voxel_size': obj.data.remesh_voxel_size,
                                 'resolution': args.voxel_resolution})
    merge_report = []
    if args.merge_coincident:
        low, high = bounds()
        tolerance = max(max(high - low) * 1e-8, 1e-12)
        for obj in [o for o in bpy.context.scene.objects if o.type == 'MESH']:
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            vertex_count = len(bm.verts)
            bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=tolerance)
            merge_report.append({'object': obj.name, 'vertices_before': vertex_count,
                                 'vertices_after': len(bm.verts), 'distance': tolerance})
            bm.to_mesh(obj.data)
            bm.free()
            obj.data.update()
    # Never edit the downloaded source. Save the derived candidate separately.
    for _ in range(12):
        current = counts()['triangles']
        if current <= args.budget:
            break
        ratio = args.budget / current * 0.98
        for obj in [o for o in bpy.context.scene.objects if o.type == 'MESH']:
            bpy.context.view_layer.objects.active = obj
            mod = obj.modifiers.new('LowpolyBudget', 'DECIMATE')
            mod.decimate_type = 'COLLAPSE'
            mod.ratio = ratio
            bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.context.view_layer.update()
    mesh_validation = []
    for obj in [o for o in bpy.context.scene.objects if o.type == 'MESH']:
        repaired = obj.data.validate(clean_customdata=True)
        obj.data.update()
        mesh_validation.append({'object': obj.name, 'invalid_data_repaired': repaired})
    after = counts()
    assert 0 < after['triangles'] <= args.budget, after
    assert after['finite_coordinates']
    final_bounds = [list(v) for v in bounds()]
    # Imported custom normals can become invalid after collapse. Recompute them
    # on the geometry-only candidate; retain the original import separately.
    bpy.ops.object.select_all(action='DESELECT')
    for obj in [o for o in bpy.context.scene.objects if o.type == 'MESH']:
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        if obj.data.has_custom_normals:
            bpy.ops.mesh.customdata_custom_splitnormals_clear()
        for polygon in obj.data.polygons:
            polygon.use_smooth = True
        obj.data.update()
        obj.select_set(False)
    # Neutral geometry previews: no claim of original or generated texture fidelity.
    mat = bpy.data.materials.new('NeutralGeometryPreview')
    mat.use_nodes = True
    mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (.32, .5, .68, 1)
    mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = .7
    for obj in [o for o in bpy.context.scene.objects if o.type == 'MESH']:
        obj.data.materials.clear()
        obj.data.materials.append(mat)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.render.resolution_x = scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    low, high = bounds()
    center = (low + high) * .5
    span = max(high - low)
    if not span > 0:
        raise ValueError('Degenerate model bounds')
    bpy.ops.object.camera_add()
    scene.camera = bpy.context.object
    scene.camera.data.type = 'ORTHO'
    scene.camera.data.ortho_scale = span * 1.25
    scene.camera.data.clip_end = max(1000, span * 100)
    for offset, energy in [((2, -3, 4), 900), ((-2, 3, 3), 600)]:
        bpy.ops.object.light_add(type='AREA', location=center + Vector(offset) * span)
        lamp = bpy.context.object
        lamp.rotation_euler = (center - lamp.location).to_track_quat('-Z', 'Y').to_euler()
        lamp.data.energy = energy * span * span
        lamp.data.size = span * 3
    for label, direction in {'front': (0, -1, 0), 'side': (1, 0, 0),
                             'back': (0, 1, 0), 'three-quarter': (1, -2, .6)}.items():
        scene.camera.location = center + Vector(direction).normalized() * span * 4
        scene.camera.rotation_euler = (center - scene.camera.location).to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = str(out / (label + '.png'))
        bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / 'lowpoly.blend'))
    bpy.ops.object.select_all(action='DESELECT')
    for obj in bpy.context.scene.objects:
        obj.select_set(obj.type == 'MESH')
    bpy.ops.export_scene.gltf(filepath=str(out / 'lowpoly.glb'), export_format='GLB', use_selection=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(out / 'lowpoly.glb'))
    roundtrip = counts()
    assert roundtrip['triangles'] == after['triangles'], (after, roundtrip)
    assert roundtrip['finite_coordinates']
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
    report = {"scope": "Generated source -> local decimation -> geometry-only GLB roundtrip",
        "source": {"path": str(source), "sha256": source_hash},
        "blender": bpy.app.version_string, "triangle_budget": args.budget,
        "before": before, "after": after, "roundtrip": roundtrip,
        "source_bounds": original_bounds, "candidate_bounds": final_bounds,
        "lowpoly_method": ("local voxel reconstruction + " if voxel_report else "local ")
                          + "Blender DECIMATE/COLLAPSE; native N4D Smart Mesh not verified",
        "coincident_vertex_merge": merge_report,
        "voxel_reconstruction": voxel_report,
        "mesh_validation": mesh_validation,
        "candidate_normals": "Imported custom normals cleared; smooth normals recomputed after decimation",
        "checks": {"triangle_budget": "pass", "finite_coordinates": "pass",
            "source_file_preserved": "pass", "glb_triangle_roundtrip": "pass",
            "reference_fidelity": "not_run", "rig": "not_run", "animation": "not_run",
            "collision": "not_run", "engine": "not_run"}}
    (out / 'lowpoly-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('LOWPOLY_PASS', after['triangles'], out)


if __name__ == '__main__':
    main()
