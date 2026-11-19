"""Blender --background --python-exit-code 1 --python assemble.py -- CASE.json OUT"""

import sys
import json
import math
import hashlib
import time
from pathlib import Path
from itertools import combinations
import bpy
from mathutils import Vector, Matrix, Euler, kdtree
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from neck import fit_neck


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def audit(objects):
    trees = {}
    for o in objects:
        mesh = o.data
        mesh.calc_loop_triangles()
        trees[o.name] = BVHTree.FromPolygons(
            [o.matrix_world @ v.co for v in mesh.vertices],
            [tuple(t.vertices) for t in mesh.loop_triangles],
            all_triangles=True,
        )
    return {
        f"{a}/{b}": len(trees[a].overlap(trees[b])) for a, b in combinations(trees, 2)
    }


def check_seam(segments):
    restored = []
    for name, edges in segments.items():
        o = bpy.data.objects[name]
        pts = [o.matrix_world @ v.co for v in o.data.vertices]
        tree = kdtree.KDTree(len(pts))
        for i, p in enumerate(pts):
            tree.insert(p, i)
        tree.balance()

        def key(v):
            return tuple(round(x, 6) for x in v)

        actual = {tuple(sorted(key(pts[i]) for i in e.vertices)) for e in o.data.edges}
        ring = []
        for a, b in edges:
            x, _, dx = tree.find(a)
            y, _, dy = tree.find(b)
            if max(dx, dy) > 1e-6 or tuple(sorted((key(x), key(y)))) not in actual:
                raise ValueError("Saved boundary edge missing")
            ring.append((x, y))
        restored.append(ring)

    def distance(p, a, b):
        d = b - a
        return (p - a - d * max(0, min(1, (p - a).dot(d) / d.length_squared))).length

    def error(first, second):
        return max(
            min(distance(a.lerp(b, t / 8), u, v) for u, v in second)
            for a, b in first
            for t in range(9)
        )

    errs = [error(*restored), error(*reversed(restored))]
    if max(errs) > 1e-6:
        raise ValueError("Saved neck perimeter mismatch")
    return {
        "edge_counts": [len(r) for r in restored],
        "max_sampled_gap_each_direction": errs,
    }


def main():
    start = time.monotonic()
    casefile, outdir = sys.argv[sys.argv.index("--") + 1 :]
    casefile = Path(casefile).resolve()
    case = json.loads(casefile.read_text())
    out = Path(outdir).resolve()
    out.mkdir(parents=True, exist_ok=False)
    ref = (casefile.parent / case["apose"]).resolve()
    report = {"reference": str(ref), "reference_sha256": sha(ref), "inputs": {}}
    bpy.ops.wm.read_factory_settings(use_empty=True)
    objs = {}
    for n, spec in case["parts"].items():
        if "receipt" in spec:
            receipt = (casefile.parent / spec["receipt"]).resolve()
            meta = json.loads(receipt.read_text())
            if meta.get("status") != "success" or meta.get("type") != "texture_model":
                raise ValueError(f"{n}: expected completed texture receipt")
            source = (receipt.parent / meta["model_file"]).resolve()
        else:
            source = (casefile.parent / spec["glb"]).resolve()
        if source.suffix.lower() != ".glb":
            raise ValueError("Expected a textured GLB")
        bpy.ops.import_scene.gltf(filepath=str(source))
        (o,) = [o for o in bpy.context.selected_objects if o.type == "MESH"]
        if o.data.shape_keys or o.modifiers or not o.data.uv_layers:
            raise ValueError(f"{n}: expected static mesh with UVs")
        if not any(
            node.type == "TEX_IMAGE" and node.image
            for slot in o.material_slots
            if slot.material and slot.material.use_nodes
            for node in slot.material.node_tree.nodes
        ):
            raise ValueError(f"{n}: missing texture")
        matrix = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = matrix
        o.name = n
        objs[n] = o
        report["inputs"][n] = {"source": str(source), "sha256": sha(source)}
        if n == case["body"]:
            if any(k in spec for k in ("center", "height", "rotation_degrees")):
                raise ValueError("Body must be the fixed anchor")
            continue
        rot = (
            Euler([math.radians(v) for v in spec.get("rotation_degrees", [0, 0, 0])])
            .to_matrix()
            .to_4x4()
        )
        pts = [rot @ matrix @ v.co for v in o.data.vertices]
        lo = Vector([min(p[i] for p in pts) for i in range(3)])
        hi = Vector([max(p[i] for p in pts) for i in range(3)])
        scale = spec["height"] / (hi.z - lo.z)
        if not math.isfinite(scale) or scale <= 0:
            raise ValueError(f"{n}: invalid height")
        o.matrix_world = (
            Matrix.Translation(Vector(spec["center"]) - scale * (lo + hi) / 2)
            @ Matrix.Scale(scale, 4)
            @ rot
            @ matrix
        )
    bpy.context.view_layer.update()
    seam = case.get("neck")
    segments = None
    if seam:
        segments = fit_neck(objs[case["body"]], objs[seam["head"]], seam)
    report["unmasked_triangle_pair_overlaps"] = audit(objs.values())
    masks = []
    for n, regions in case.get("keep_visible", {}).items():
        obj = objs[n]
        group = obj.vertex_groups.new(name="Visible when dressed")
        for v in obj.data.vertices:
            x, y, z = obj.matrix_world @ v.co
            values = {"x": x, "y": y, "abs_y": abs(y), "z": z}
            if any(
                all(lo <= values[k] <= hi for k, (lo, hi) in region.items())
                for region in regions
            ):
                group.add([v.index], 1, "REPLACE")
        mask = obj.modifiers.new("Clothed display only", "MASK")
        mask.vertex_group = group.name
        masks.append(mask)
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.color_type = "TEXTURE"
    sh.light = "FLAT"
    sh.background_type = "WORLD"
    sc.world = bpy.data.worlds.new("Gray")
    sc.world.color = (0.14,) * 3
    sc.view_settings.view_transform = "Standard"
    sc.render.resolution_x = sc.render.resolution_y = 640
    sc.render.resolution_percentage = 100
    bpy.ops.object.camera_add()
    cam = bpy.context.object
    sc.camera = cam
    cam.data.type = "ORTHO"
    front = Vector(case["front"])
    front.z = 0
    front.normalize()
    if not front.length:
        raise ValueError("Expected a horizontal front direction")
    left = Vector((-front.y, front.x, 0))
    views = [("front", front), ("left", left), ("back", -front), ("right", -left)]

    def render(prefix, frame, directions=views):
        for name, axis in directions:
            cam.location = Vector(frame["center"]) + 4 * frame["scale"] * axis
            cam.rotation_euler = (-axis).to_track_quat("-Z", "Y").to_euler()
            cam.data.ortho_scale = frame["scale"]
            sc.render.filepath = str(out / (prefix + "-" + name + ".png"))
            bpy.ops.render.render(write_still=True)
            if prefix == "full" and name == "front":
                bpy.ops.file.pack_all()
                bpy.ops.wm.save_as_mainfile(filepath=str(out / "assembly.blend"))

    render("full", case["frame"])
    review_props = [objs[n] for n in case.get("review_hide_props", [])]
    for prop in review_props:
        prop.hide_render = True
    if review_props:
        render("character", case["frame"])
    if "hair_frame" in case:
        render("head-hair", case["hair_frame"])
    for prop in review_props:
        prop.hide_render = False
    for m in masks:
        m.show_render = False
    if masks:
        render("unmasked", case["frame"])
    if case.get("review_part_colors"):
        import colorsys

        for i, obj in enumerate(objs.values()):
            obj.color = (*colorsys.hsv_to_rgb((i * 0.618034) % 1, 0.7, 0.9), 1)
        sh.color_type = "OBJECT"
        for prop in review_props:
            prop.hide_render = True
        render("part-colors", case["frame"])
        sh.color_type = "TEXTURE"
        for prop in review_props:
            prop.hide_render = False
    if seam:
        for name in seam["hide"]:
            objs[name].hide_render = True
        diagonals = [
            ("front-left", (front + left).normalized()),
            ("back-left", (-front + left).normalized()),
            ("back-right", (-front - left).normalized()),
            ("front-right", (front - left).normalized()),
        ]
        render("neck", seam["frame"], views + diagonals)
        report["neck_visual_review"] = {
            "status": "pending",
            "views": [f"neck-{name}.png" for name, _ in views + diagonals],
        }
    bpy.ops.wm.open_mainfile(filepath=str(out / "assembly.blend"))
    if segments:
        report["neck_readback"] = check_seam(segments)
        counts = report["neck_readback"]["edge_counts"]
        report["neck_readback"]["edge_correspondence"] = (
            "failed_edge_count" if counts[0] != counts[1] else "pending_verification"
        )
    for n in objs:
        obj = bpy.data.objects[n]
        if any(
            not node.image.packed_file
            for s in obj.material_slots
            if s.material and s.material.use_nodes
            for node in s.material.node_tree.nodes
            if node.type == "TEX_IMAGE" and node.image
        ):
            raise ValueError("External texture dependency")
    report["display_masks"] = list(case.get("keep_visible", {}))
    report["execution_seconds"] = time.monotonic() - start
    (out / "report.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
