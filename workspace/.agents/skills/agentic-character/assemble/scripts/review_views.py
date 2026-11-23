"""Open a saved scene once and inspect camera-matched full and local views."""
import argparse
from functools import lru_cache
import json
import math
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from refine_contacts import audit, meshes
from clearance import surface, tree
from preflight import check_regions


def region_contacts(objects, spec, geometry=surface, garment_tree=None):
    """Intersect the fixed surface inside a world-space box with the entire garment."""
    lo, hi = np.asarray(spec["bounds"], dtype=float)
    if lo.shape != (3,) or hi.shape != (3,) or not np.all(np.isfinite([lo, hi])) or np.any(lo >= hi):
        raise ValueError("Expected finite world-space minimum and maximum corners")
    if spec["fixed"] == spec["garment"]:
        raise ValueError("Select two distinct meshes")
    p, faces = geometry(objects[spec["fixed"]])
    triangles = p[faces]
    candidates = np.all((triangles.max(1) >= lo) & (triangles.min(1) <= hi), axis=1)
    vertices, indices, sources = [], [], []
    for source in np.flatnonzero(candidates):
        polygon = list(triangles[source])
        for axis in range(3):
            for bound, sign in ((lo[axis], 1), (hi[axis], -1)):
                clipped = []
                for a, b in zip(polygon, polygon[1:] + polygon[:1]):
                    da, db = sign*(a[axis]-bound), sign*(b[axis]-bound)
                    if da >= 0:
                        clipped.append(a)
                    if da * db < 0:
                        clipped.append(a + (b-a)*(da/(da-db)))
                polygon = clipped
        start = len(vertices)
        vertices.extend(polygon)
        for i in range(1, len(polygon)-1):
            if np.any(np.cross(polygon[i]-polygon[0], polygon[i+1]-polygon[0])):
                indices.append((start, start+i, start+i+1))
                sources.append(int(source))
    if not indices:
        raise ValueError("Contact box contains no fixed surface")
    clipped_tree = tree(np.asarray(vertices), np.asarray(indices))
    garment = objects[spec["garment"]]
    target = garment_tree(garment) if garment_tree else tree(*geometry(garment))
    pairs = clipped_tree.overlap(target)
    return dict(fixed_faces=len(set(sources)), triangle_pairs=len({(sources[i], j) for i,j in pairs}),
                visual_review="pending")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--focus", nargs="+", metavar="FRAME=VIEW")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    plan = json.loads(args.plan.read_text())
    directions = ("front", "front_left", "left", "back_left",
                  "back", "back_right", "right", "front_right")
    focus = {}
    for item in args.focus or ():
        frame, _, view = item.partition("=")
        if frame not in plan["frames"] or view not in directions:
            parser.error(f"Unknown frame or direction: {item}")
        if directions.index(view) % 2 and not plan["frames"][frame].get("diagonals"):
            parser.error(f"Diagonal view is disabled for {frame}")
        focus.setdefault(frame, set()).add(view)
    out = args.destination.resolve()
    out.mkdir(parents=True, exist_ok=False)
    scene = bpy.context.scene
    objects = meshes()
    geometry = lru_cache(maxsize=None)(surface)
    if "geometry_limits" in plan:
        check_regions(plan["geometry_limits"], args.plan.resolve().parent, out,
                      lambda name: geometry(objects[name]))
    if focus:
        if any(o.hide_render or any(m.type == "MASK" for m in o.modifiers) for o in objects.values()):
            raise ValueError("Focused reviews require the full unmasked scene")
        report = {"scope": "local_iteration"}
    else:
        report = audit(objects)
    @lru_cache(maxsize=None)
    def garment_tree(obj):
        return tree(*geometry(obj))
    camera = scene.camera
    if camera is None or camera.data.type != "ORTHO":
        raise ValueError("Select an orthographic review camera")
    front = Vector(plan["front"])
    front.z = 0
    if not front.length:
        raise ValueError("Provide a horizontal front direction")
    front.normalize()
    left = Vector((-front.y, front.x, 0))
    rendered = []
    for label, frame in plan["frames"].items():
        if focus and label not in focus:
            continue
        if not label.isidentifier() or frame['scale'] <= 0:
            raise ValueError("Invalid frame name or scale")
        center = Vector(frame["center"])
        camera.data.ortho_scale = frame["scale"]
        hidden = [objects[n] for n in frame.get("hide", [])]
        if "contact" in frame:
            spec = frame["contact"]
            if {spec["fixed"], spec["garment"]}.intersection(frame.get("hide", [])):
                raise ValueError("Both contact surfaces must be visible in the review frame")
            report.setdefault("region_contacts", {})[label] = region_contacts(objects, spec, geometry, garment_tree)
        try:
            for obj in hidden:
                obj.hide_render = True
            for index, name in enumerate(directions):
                if focus and name not in focus[label]:
                    continue
                if index % 2 and not frame.get("diagonals"):
                    continue
                angle = math.pi * index / 4
                axis = front * math.cos(angle) + left * math.sin(angle)
                camera.location = center + 4 * frame["scale"] * axis
                camera.rotation_euler = (-axis).to_track_quat("-Z", "Y").to_euler()
                filename = f"{label}-{name}.png"
                scene.render.filepath = str(out / filename)
                scene.render.image_settings.file_format = 'PNG'
                bpy.ops.render.render(write_still=True)
                rendered.append(filename)
        finally:
            for obj in hidden:
                obj.hide_render = False
    report.update(frames=plan, images=rendered)
    if focus:
        report["reviewed_views"] = {label: sorted(views) for label, views in focus.items()}
    (out / "geometry.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
