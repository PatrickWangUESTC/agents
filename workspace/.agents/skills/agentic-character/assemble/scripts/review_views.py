"""Open a saved scene once and inspect camera-matched full and local views."""
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from refine_contacts import audit, meshes


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
