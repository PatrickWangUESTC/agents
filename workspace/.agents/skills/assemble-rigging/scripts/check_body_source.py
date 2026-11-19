"""Compare the assembled body's rest rig and skin with its reviewed donor."""
import json
import sys
from pathlib import Path

import bpy
import numpy as np


def snapshot(path, names):
    bpy.ops.wm.open_mainfile(filepath=str(path), load_ui=False)
    body = bpy.context.scene.objects["body"]
    mods = [m for m in body.modifiers if m.type == "ARMATURE" and m.show_viewport]
    if len(mods) != 1 or mods[0].object is None:
        raise ValueError(f"{path}: expected one active body armature")
    rig = mods[0].object
    transform = body.matrix_world.inverted() @ rig.matrix_world
    bones = [rig.data.bones[name] for name in names]
    vertices = np.array([tuple(v.co) for v in body.data.vertices])
    weights = np.zeros((len(vertices), len(names)))
    columns = {g.index: names.index(g.name) for g in body.vertex_groups if g.name in names}
    for v in body.data.vertices:
        for group in v.groups:
            if group.group in columns:
                weights[v.index, columns[group.group]] = group.weight
    return dict(vertices=vertices, weights=weights,
                topology=[tuple(f.vertices) for f in body.data.polygons],
                matrices=np.array([np.array(transform @ b.matrix_local) for b in bones]),
                tails=np.array([tuple(transform @ b.tail_local) for b in bones]),
                parents=[b.parent.name if b.parent else None for b in bones],
                preserve_volume=mods[0].use_deform_preserve_volume)


def main():
    donor, candidate = [Path(s).resolve(strict=True) for s in sys.argv[sys.argv.index("--") + 1:]]
    schema = Path(__file__).resolve().parents[2] / "agentic-character/rigging/human-rigging/assets/HumanArmature.json"
    names = [b["name"] for b in json.loads(schema.read_text())["bones"]]
    ref, cur = (snapshot(path, names) for path in (donor, candidate))
    changed = []
    for field, a in ref.items():
        b = cur[field]
        if isinstance(a, np.ndarray):
            if a.shape != b.shape or not np.allclose(a, b, rtol=0, atol=1e-6):
                changed.append(field)
        elif a != b:
            changed.append(field)
    hip = names.index("DEF-Left leg")
    print("Left hip in mesh space:", ref["matrices"][hip, :3, 3], cur["matrices"][hip, :3, 3], flush=True)
    if changed:
        raise ValueError("Body source mismatch: " + ", ".join(changed))
    print("Body rest rig, mesh and weights match. Verify the posed body separately.")


if __name__ == "__main__":
    main()
