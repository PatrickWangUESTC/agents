"""Open a saved scene once and inspect camera-matched full and local views."""
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


def region_contacts(objects, spec):
    """Intersect the fixed surface inside a world-space box with the entire garment."""
    lo, hi = np.asarray(spec["bounds"], dtype=float)
    if lo.shape != (3,) or hi.shape != (3,) or not np.all(np.isfinite([lo, hi])) or np.any(lo >= hi):
        raise ValueError("Expected finite world-space minimum and maximum corners")
    if spec["fixed"] == spec["garment"]:
        raise ValueError("Select two distinct meshes")
    p, faces = surface(objects[spec["fixed"]])
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
    pairs = clipped_tree.overlap(tree(*surface(objects[spec["garment"]])))
    return dict(fixed_faces=len(set(sources)), triangle_pairs=len({(sources[i], j) for i,j in pairs}),
                visual_review="pending")


def main():
    plan_path, destination = sys.argv[sys.argv.index("--") + 1:]
    plan = json.loads(Path(plan_path).read_text())
    out = Path(destination).resolve()
    out.mkdir(parents=True, exist_ok=False)
    scene = bpy.context.scene
    objects = meshes()
    report = audit(objects)
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
        if not label.isidentifier() or frame['scale'] <= 0:
            raise ValueError("Invalid frame name or scale")
        center = Vector(frame["center"])
        camera.data.ortho_scale = frame["scale"]
        hidden = [objects[n] for n in frame.get("hide", [])]
        if "contact" in frame:
            spec = frame["contact"]
            if {spec["fixed"], spec["garment"]}.intersection(frame.get("hide", [])):
                raise ValueError("Both contact surfaces must be visible in the review frame")
            report.setdefault("region_contacts", {})[label] = region_contacts(objects, spec)
        try:
            for obj in hidden:
                obj.hide_render = True
            for index, name in enumerate(("front", "front_left", "left", "back_left",
                                          "back", "back_right", "right", "front_right")):
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
    (out / "geometry.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
