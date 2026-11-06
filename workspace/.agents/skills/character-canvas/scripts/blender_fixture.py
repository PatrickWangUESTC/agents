"""Blender 4.3+ integration fixture, NOT a generated or game-ready character.

blender --background --factory-startup --python blender_fixture.py -- OUTPUT_DIR
"""
import hashlib
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector


def signature(obj):
    payload = {
        "matrix": [list(row) for row in obj.matrix_world],
        "vertices": [list(v.co) for v in obj.data.vertices],
        "faces": [list(p.vertices) for p in obj.data.polygons],
        "material_indices": [p.material_index for p in obj.data.polygons],
        "uvs": [[list(d.uv) for d in layer.data] for layer in obj.data.uv_layers],
        "materials": [{"name": m.name, "color": list(m.diffuse_color),
                       "nodes": [(n.name, n.type) for n in m.node_tree.nodes]
                       if m.use_nodes else []} for m in obj.data.materials],
        "modifiers": [(m.name, m.type) for m in obj.modifiers],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def inventory():
    return {o.name: {"dimensions": list(o.dimensions),
                     "materials": [m.name for m in o.data.materials]}
            for o in bpy.context.scene.objects if o.type == "MESH"}


def render_views(out, prefix):
    scene = bpy.context.scene
    for label, location in {"front": (0, -7, 1.6), "side": (7, 0, 1.6),
                            "back": (0, 7, 1.6)}.items():
        scene.camera.location = location
        scene.camera.rotation_euler = (Vector((0, 0, 1.3)) - scene.camera.location).to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = str(out / f"{prefix}-{label}.png")
        bpy.ops.render.render(write_still=True)


def main():
    out = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
    out.mkdir(parents=True, exist_ok=False)
    sources = out / "source-parts"
    sources.mkdir()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    specs = {
        "body": ((0, 0, 1.0), (.3, .2, .75), (.32, .42, .65, 1)),
        "clothing": ((0, -.03, 1.35), (.35, .24, .35), (.18, .65, .35, 1)),
        "shoes": ((0, -.08, .15), (.36, .32, .15), (.12, .13, .17, 1)),
        "head": ((0, 0, 2.02), (.27, .24, .3), (.8, .58, .4, 1)),
    }
    for name, (location, scale, color) in specs.items():
        bpy.ops.mesh.primitive_cube_add(size=2, location=location)
        obj = bpy.context.object
        obj.name = name
        obj.scale = scale
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        mat = bpy.data.materials.new(name + "_material")
        mat.diffuse_color = color
        mat.use_nodes = True
        mat.node_tree.nodes.get("Principled BSDF").inputs["Base Color"].default_value = color
        obj.data.materials.append(mat)
        bpy.data.libraries.write(str(sources / f"{name}.blend"), {obj})
        bpy.data.objects.remove(obj, do_unlink=True)
    source_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources.iterdir()}
    # Actual assembly from separate saved Blender libraries.
    for name in specs:
        with bpy.data.libraries.load(str(sources / f"{name}.blend"), link=False) as (available, loaded):
            loaded.objects = [name]
        for obj in loaded.objects:
            bpy.context.collection.objects.link(obj)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 384
    scene.render.resolution_y = 384
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    bpy.ops.object.camera_add()
    scene.camera = bpy.context.object
    scene.camera.data.type = "ORTHO"
    scene.camera.data.ortho_scale = 3.1
    bpy.ops.object.light_add(type='AREA', location=(2, -4, 5))
    bpy.context.object.data.energy = 700
    bpy.context.object.data.shape = 'DISK'
    bpy.context.object.data.size = 5
    bpy.ops.object.light_add(type='AREA', location=(-2, 3, 4))
    bpy.context.object.data.energy = 500
    bpy.context.object.data.size = 5
    bpy.context.view_layer.update()
    before = {n: signature(bpy.data.objects[n]) for n in specs}
    render_views(out, "baseline")
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "baseline.blend"))
    # A real local edit, scoped to head geometry in a separate saved candidate.
    head = bpy.data.objects["head"]
    head.data = head.data.copy()
    for vertex in head.data.vertices:
        vertex.co.x *= 1.25
    bpy.context.view_layer.update()
    after = {n: signature(bpy.data.objects[n]) for n in specs}
    protected = [n for n in specs if n != "head"]
    assert all(before[n] == after[n] for n in protected)
    assert before["head"] != after["head"]
    render_views(out, "candidate")
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "candidate.blend"))
    expected = inventory()
    bpy.ops.export_scene.gltf(filepath=str(out / "candidate.glb"), export_format='GLB')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(out / "candidate.glb"))
    observed = inventory()
    assert set(expected) == set(observed), (expected, observed)
    for name in expected:
        assert expected[name]["materials"] == observed[name]["materials"]
        assert all(abs(a-b) < 1e-5 for a, b in zip(expected[name]["dimensions"], observed[name]["dimensions"]))
    assert source_hashes == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources.iterdir()}
    report = {
        "scope": "Procedural cube mannequin fixture; not character generation or game-ready validation",
        "blender_version": bpy.app.version_string,
        "checks": {"separate_part_library_assembly": "pass", "head_changed": "pass",
                   "protected_part_signatures": "pass", "source_part_files_unchanged": "pass",
                   "glb_part_names_material_names_dimensions": "pass",
                   "rig_and_skin_weights": "not_run", "animation": "not_run",
                   "target_engine": "not_run", "intersection_clearance": "not_run",
                   "reference_fidelity": "not_run"},
        "protected_parts": protected, "before": before, "after": after,
        "roundtrip_before": expected, "roundtrip_after": observed,
        "preservation_scope": "Transforms, vertices, faces, UVs, polygon material indices, material names/colors/node types and modifier names/types; no rig or morphs in fixture",
    }
    (out / "fixture-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print("CHARACTER_FIXTURE_PASS", out)


if __name__ == "__main__":
    main()
