"""Blender worker for local AI-Lab-style assembly. See lab.py for validation."""
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector
from mathutils.bvhtree import BVHTree


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def signature(obj):
    mesh = obj.data
    co = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", co)
    indices = np.empty(len(mesh.loops), dtype=np.int32)
    mesh.loops.foreach_get("vertex_index", indices)
    uvs = {}
    for layer in mesh.uv_layers:
        arr = np.empty(len(mesh.loops) * 2, dtype=np.float32)
        layer.data.foreach_get("uv", arr)
        uvs[layer.name] = hashlib.sha256(arr.tobytes()).hexdigest()
    mesh.calc_loop_triangles()
    return {"vertices": len(mesh.vertices), "triangles": len(mesh.loop_triangles),
            "coordinates": hashlib.sha256(co.tobytes()).hexdigest(),
            "indices": hashlib.sha256(indices.tobytes()).hexdigest(), "uv": uvs,
            "finite": bool(np.isfinite(co).all()),
            "materials": [m.name if m else None for m in mesh.materials],
            "shape_keys": list(mesh.shape_keys.key_blocks.keys()) if mesh.shape_keys else [],
            "modifiers": [m.type for m in obj.modifiers]}


def bounds(objects):
    cs = [o.matrix_world @ Vector(c) for o in objects for c in o.bound_box]
    lo = Vector([min(v[i] for v in cs) for i in range(3)])
    hi = Vector([max(v[i] for v in cs) for i in range(3)])
    return lo, hi


def fit(obj, profile):
    """Case-reviewed smooth horizontal fit in imported world space; UV unchanged.
    Rows: [z, x_scale, y_scale, x_offset, y_offset]. End rows clamp.
    """
    if not profile:
        return
    if obj.data.shape_keys or obj.modifiers or obj.parent and obj.parent.type == 'ARMATURE':
        raise ValueError("Fit profiles currently support unrigged static meshes only")
    local = np.empty(len(obj.data.vertices) * 3, dtype=np.float32)
    obj.data.vertices.foreach_get("co", local)
    local = local.reshape(-1, 3)
    mat = np.array(obj.matrix_world, dtype=np.float64)
    world = np.einsum('ij,nj->ni', mat[:3, :3], local) + mat[:3, 3]
    rows = np.asarray(profile)
    params = [np.interp(world[:, 2], rows[:, 0], rows[:, i]) for i in range(1, 5)]
    world[:, 0] = world[:, 0] * params[0] + params[2]
    world[:, 1] = world[:, 1] * params[1] + params[3]
    inv = np.array(obj.matrix_world.inverted(), dtype=np.float64)
    changed = np.einsum('ij,nj->ni', inv[:3, :3], world) + inv[:3, 3]
    if not np.isfinite(changed).all():
        raise ValueError("Non-finite fit output")
    obj.data.vertices.foreach_set("co", changed.astype(np.float32).ravel())
    obj.data.update()


def world_vertices(obj):
    values = np.empty(len(obj.data.vertices) * 3, dtype=np.float32)
    obj.data.vertices.foreach_get('co', values)
    mat = np.array(obj.matrix_world, dtype=np.float64)
    return np.einsum('ij,nj->ni', mat[:3, :3], values.reshape(-1, 3)) + mat[:3, 3]


def collider(objects, options):
    positions, faces, offset = [], [], 0
    retained, excluded = 0, 0
    for obj in objects:
        if obj.data.shape_keys or obj.modifiers:
            raise ValueError('Clearance target must be a static mesh')
        mesh = obj.data
        mesh.calc_loop_triangles()
        triangles = np.empty(len(mesh.loop_triangles) * 3, dtype=np.int32)
        mesh.loop_triangles.foreach_get('vertices', triangles)
        triangles = triangles.reshape(-1, 3)
        keep = np.ones(len(triangles), dtype=bool)
        if options.get('target_filter') == 'neutral_albedo':
            # Explicit case-specific mask: this character has a neutral gray suit
            # and purple hair. This is not an anatomical segmentation algorithm.
            mats = [m for m in mesh.materials if m]
            if len(mats) != 1 or not mesh.uv_layers.active:
                raise ValueError('Neutral albedo mask needs one textured material with UVs')
            bsdf = next(n for n in mats[0].node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
            links = bsdf.inputs['Base Color'].links
            if len(links) != 1 or links[0].from_node.type != 'TEX_IMAGE':
                raise ValueError('Neutral mask requires a direct base-color image')
            img = links[0].from_node.image
            pixels = np.empty(len(img.pixels), dtype=np.float32)
            img.pixels.foreach_get(pixels)
            pixels = pixels.reshape(img.size[1], img.size[0], 4)
            uv = np.empty(len(mesh.loops) * 2, dtype=np.float32)
            mesh.uv_layers.active.data.foreach_get('uv', uv)
            loops = np.empty(len(triangles) * 3, dtype=np.int32)
            mesh.loop_triangles.foreach_get('loops', loops)
            uv = uv.reshape(-1, 2)[loops.reshape(-1, 3)].mean(axis=1)
            x = np.clip((uv[:, 0] * img.size[0]).astype(int), 0, img.size[0] - 1)
            y = np.clip((uv[:, 1] * img.size[1]).astype(int), 0, img.size[1] - 1)
            rgb = pixels[y, x, :3]
            keep = (rgb.max(axis=1) / np.maximum(rgb.min(axis=1), .01) < options['max_channel_ratio']) & (rgb.max(axis=1) > .08)
        positions.extend(world_vertices(obj).tolist())
        faces.extend((triangles[keep] + offset).tolist())
        retained += int(keep.sum())
        excluded += int((~keep).sum())
        offset += len(mesh.vertices)
    if not faces:
        raise ValueError('Empty collider')
    return BVHTree.FromPolygons(positions, faces, all_triangles=True), {'triangles_retained': retained, 'triangles_excluded': excluded}


def smooth_field(points, displacement, cell):
    """Trilinear splat/sample of a locally smoothed displacement field, no remesh."""
    origin = points.min(axis=0) - 3 * cell
    grid_co = (points - origin) / cell
    base = np.floor(grid_co).astype(int)
    fraction = grid_co - base
    shape = tuple((base.max(axis=0) + 5).tolist())
    if math.prod(shape) > 2_000_000:
        raise ValueError('Smoothing grid too dense; increase smoothing_cell')
    field = np.zeros(shape + (4,), dtype=np.float64)
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                d = np.array([dx, dy, dz])
                weight = np.prod(np.where(d, fraction, 1 - fraction), axis=1)
                ix = tuple((base + d).T)
                for axis in range(3):
                    np.add.at(field[..., axis], ix, displacement[:, axis] * weight)
                np.add.at(field[..., 3], ix, weight)
    for _ in range(2):
        for axis in range(3):
            field = (np.roll(field, 1, axis=axis) + field * 2 + np.roll(field, -1, axis=axis)) / 4
    field[..., :3] /= np.maximum(field[..., 3:4], 1e-12)
    result = np.zeros_like(points)
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                d = np.array([dx, dy, dz])
                weight = np.prod(np.where(d, fraction, 1 - fraction), axis=1)
                result += field[tuple((base + d).T)][..., :3] * weight[:, None]
    return result


def clearance(objects, tree, options):
    results = []
    margin, maximum = options['margin'], options['max_displacement']
    for obj in objects:
        if obj.data.shape_keys or obj.modifiers:
            raise ValueError('Clearance supports static unrigged meshes only')
        initial = world_vertices(obj)
        current = initial.copy()
        moved, capped, iteration_counts = set(), set(), []
        for _ in range(options.get('iterations', 2)):
            proposed = current.copy()
            negative = 0
            for i, co in enumerate(current):
                near, normal, face, distance = tree.find_nearest(Vector(co), maximum * 2)
                if near is None:
                    continue
                signed = (Vector(co) - near).dot(normal)
                negative += int(signed < 0)
                if signed < margin:
                    proposal = np.array(near + normal * margin)
                    displacement = float(np.linalg.norm(proposal - initial[i]))
                    if displacement > maximum:
                        capped.add(i)
                        continue
                    proposed[i] = proposal
                    moved.add(i)
            iteration_counts.append(negative)
            displacement = proposed - current
            if options.get('smoothing_cell'):
                displacement = smooth_field(current, displacement, options['smoothing_cell'])
            total = current + displacement - initial
            length = np.linalg.norm(total, axis=1)
            total *= np.minimum(1, maximum / np.maximum(length, 1e-12))[:, None]
            current = initial + total
        inv = np.array(obj.matrix_world.inverted(), dtype=np.float64)
        local = np.einsum('ij,nj->ni', inv[:3, :3], current) + inv[:3, 3]
        assert np.isfinite(local).all()
        obj.data.vertices.foreach_set('co', local.astype(np.float32).ravel())
        obj.data.update()
        results.append({'object': obj.name, 'vertices_moved': len(moved), 'vertices_capped': len(capped),
                        'negative_side_vertices_at_iteration_start': iteration_counts,
                        'max_displacement': float(np.linalg.norm(current - initial, axis=1).max()),
                        'scope': 'Nearest oriented surface projection; not a global collision-free certificate'})
    return results


def main():
    path = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
    out, config = path.parent, json.loads(path.read_text())
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    records, all_meshes, roots, by_part = [], [], [], {}
    for part in config["parts"]:
        source = Path(part["source"])
        if sha(source) != part["source_sha256"]:
            raise ValueError("Input changed after validation")
        before = set(scene.objects)
        bpy.ops.import_scene.gltf(filepath=str(source))
        imported = set(scene.objects) - before
        meshes = sorted([o for o in imported if o.type == "MESH"], key=lambda o: o.name)
        if not meshes:
            raise ValueError(f"No geometry: {part['name']}")
        bpy.context.view_layer.update()
        initial_bounds = bounds(meshes)
        native = {o: signature(o) for o in meshes}
        for obj in meshes:
            fit(obj, part.get("fit_profile", []))
        root = bpy.data.objects.new(part["name"], None)
        scene.collection.objects.link(root)
        roots.append(root)
        for obj in imported:
            if obj.parent not in imported:
                matrix = obj.matrix_world.copy()
                obj.parent = root
                obj.matrix_world = matrix
        root.matrix_world = (Matrix.Translation(Vector(part["translation"])) @
            Euler([math.radians(a) for a in part["rotation_degrees"]], "XYZ").to_matrix().to_4x4() @
            Matrix.Diagonal(Vector(part["scale"] + [1])))
        bpy.context.view_layer.update()
        for i, obj in enumerate(meshes):
            obj.name = f"{part['name']}_{i:02d}"
            obj["part_id"] = part["name"]
            after = signature(obj)
            assert native[obj]["indices"] == after["indices"]
            assert native[obj]["uv"] == after["uv"]
            assert native[obj]["materials"] == after["materials"]
            if not part.get("fit_profile"):
                assert native[obj]["coordinates"] == after["coordinates"]
            records.append({"part": part["name"], "object": obj.name,
                "source_sha256": part["source_sha256"], "before": native[obj], "after": after,
                "source_bounds": [list(v) for v in initial_bounds],
                "fitted_bounds": [list(v) for v in bounds([obj])],
                "fit_profile": part.get("fit_profile", [])})
        all_meshes.extend(meshes)
        by_part[part['name']] = meshes
    contacts = []
    for part in config['parts']:
        options = part.get('surface_clearance')
        if options:
            tree, mask_info = collider(by_part[options['target']], options)
            contacts.append({'part': part['name'], 'target': options['target'], 'mask': mask_info,
                             'result': clearance(by_part[part['name']], tree, options)})
            del tree
        for edit in part.get('local_offsets', []):
            for obj in by_part[part['name']]:
                if obj.data.shape_keys or obj.modifiers:
                    raise ValueError('Local offsets support static meshes only')
                world = world_vertices(obj)
                radius, center = np.array(edit['radius']), np.array(edit['center'])
                weight = np.exp(-.5 * np.sum(((world - center) / radius) ** 2, axis=1))
                world += weight[:, None] * np.array(edit['delta'])
                inv = np.array(obj.matrix_world.inverted(), dtype=np.float64)
                local = np.einsum('ij,nj->ni', inv[:3, :3], world) + inv[:3, 3]
                assert np.isfinite(local).all()
                obj.data.vertices.foreach_set('co', local.astype(np.float32).ravel())
                obj.data.update()
    bpy.context.view_layer.update()
    for record in records:
        obj = bpy.data.objects[record['object']]
        record['after'] = signature(obj)
        assert record['before']['indices'] == record['after']['indices']
        assert record['before']['uv'] == record['after']['uv']
        part = next(p for p in config['parts'] if p['name'] == record['part'])
        if part.get('protected_geometry'):
            assert record['before'] == record['after']
    # A presentation scale, not a measured height from the image.
    lo, hi = bounds(all_meshes)
    factor = config["display_height_m"] / (hi.z - lo.z)
    assembly = bpy.data.objects.new("CHARACTER_ASSEMBLY", None)
    scene.collection.objects.link(assembly)
    for root in roots:
        root.parent = assembly
    assembly.scale = (factor,) * 3
    assembly.location.z = -lo.z * factor
    scene.unit_settings.system = "METRIC"
    bpy.context.view_layer.update()
    lo, hi = bounds(all_meshes)
    center, span = (lo + hi) / 2, max(hi - lo)
    scene.world = bpy.data.worlds.new("InspectionWorld")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs['Color'].default_value = (.22, .25, .3, 1)
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = .4
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.name = "ReviewCamera"
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = span * 1.17
    scene.camera = camera
    scene.render.resolution_x = 900
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = True
    scene.view_settings.view_transform = 'AgX'
    for offset, energy in [((2, -3, 4), 180), ((-2, -1, 2), 120), ((0, 3, 3), 100)]:
        bpy.ops.object.light_add(type="AREA", location=center + Vector(offset) * span)
        obj = bpy.context.object
        obj.data.energy, obj.data.size = energy * span * span, span * 3
        obj.rotation_euler = (center - obj.location).to_track_quat('-Z', 'Y').to_euler()
    for mode in ["native", "parts"]:
        scene.render.engine = "BLENDER_EEVEE_NEXT" if mode == "native" else "BLENDER_WORKBENCH"
        if mode == "parts":
            scene.display.shading.color_type = 'OBJECT'
            scene.display.shading.show_shadows = True
            colors = [(0.22, .55, .8, 1), (.8, .3, .12, 1), (.4, .8, .3, 1)]
            for obj in all_meshes:
                obj.color = colors[[p['name'] for p in config['parts']].index(obj['part_id']) % len(colors)]
        for label, direction in {"front": (0, -1, 0), "side": (1, 0, 0),
                                 "back": (0, 1, 0), "quarter": (1, -2, .15)}.items():
            camera.location = center + Vector(direction).normalized() * span * 4
            camera.rotation_euler = (center - camera.location).to_track_quat('-Z', 'Y').to_euler()
            scene.render.filepath = str(out / f"{mode}-{label}.png")
            bpy.ops.render.render(write_still=True)
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    bpy.ops.object.select_all(action="DESELECT")
    for obj in all_meshes + roots + [assembly]:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = all_meshes[0]
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "assembly.blend"))
    bpy.ops.export_scene.gltf(filepath=str(out / "assembly.glb"), export_format='GLB',
        use_selection=True, export_normals=False, export_yup=True, export_cameras=False,
        export_lights=False)
    bpy.ops.wm.open_mainfile(filepath=str(out / 'assembly.blend'))
    for record in records:
        assert signature(bpy.data.objects[record['object']]) == record['after']
    # Read the export in a clean scene, not the original in-memory objects.
    expected_triangles = sum(r["after"]["triangles"] for r in records)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(out / "assembly.glb"))
    imported = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    roundtrip = {o.name: signature(o) for o in imported}
    assert sum(r['triangles'] for r in roundtrip.values()) == expected_triangles
    assert set(roundtrip) == {r['object'] for r in records}
    assert all(r['finite'] and r['uv'] and r['materials'] for r in roundtrip.values())
    assert all(sha(p['source']) == p['source_sha256'] for p in config['parts'])
    report = {"scope": "Static local assembly; no provider AI 3D Lab executed",
        "blender": bpy.app.version_string, "records": records, "roundtrip": roundtrip,
        "surface_clearance": contacts,
        "bounds_m": [list(lo), list(hi)], "height_is_assumed": True,
        "triangles": expected_triangles, "missing_parts": config.get("missing_parts", []),
        "outputs": {f: sha(out / f) for f in ['assembly.blend', 'assembly.glb']},
        "checks": {"source_preserved": "pass", "uv_and_topology_preserved_during_edit": "pass",
            "native_scene_readback": "pass",
            "named_parts_roundtrip": "pass", "triangle_count_roundtrip": "pass",
            "visual_review": "not_run", "collision_free": "unknown",
            "complete_character": "fail" if config.get('missing_parts') else "unknown",
            "rig": "not_run", "animation": "not_run"}}
    (out / "inspection.json").write_text(json.dumps(report, indent=2) + '\n')
    print("ASSEMBLY_PRODUCED", expected_triangles)


if __name__ == '__main__':
    main()
