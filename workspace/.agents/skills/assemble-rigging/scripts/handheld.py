"""Seat a separate handheld prop in the rest palm and bind it to its wrist."""
import re

import bpy
import numpy as np
from mathutils import Matrix, Vector


def check_handhelds(rig, repair=False):
    reports = {}
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH" or obj.find_armature() != rig:
            continue
        name = re.sub(r"([a-z])([A-Z])", r"\1 \2", obj.name).lower()
        tokens = set(re.findall(r"[a-z]+", name))
        grip_marker = obj.get("grip_local")
        if grip_marker is None and not (tokens & {"sword", "sabre", "wand"} or "手持剑" in name or name == "剑"):
            continue
        if tokens & {"sheath", "scabbard", "sheathed", "belt", "backpack", "body", "head", "hair", "dress", "boots"}:
            continue
        p = np.array([obj.matrix_world @ v.co for v in obj.data.vertices])
        if grip_marker is not None:
            grips = [np.array(obj.matrix_world @ Vector(grip_marker))]
        else:
            axis = np.linalg.svd(p - p.mean(0), full_matrices=False)[2][0]
            u = np.sum((p - p.mean(0)) * axis, axis=1)
            width = .15 * np.ptp(u)
            grips = [np.median(p[mask], axis=0) for mask in (u <= u.min()+width, u >= u.max()-width)]
        candidates = []
        for side, suffix in (("Left", "L"), ("Right", "R")):
            if obj.get("grip_hand", side) != side:
                continue
            wrist = rig.data.bones.get(f"DEF-{side} wrist")
            if wrist is None:
                continue
            knuckles = [rig.data.bones.get(f"DEF-{finger}1_{suffix}") for finger in
                        ("IndexFinger", "MiddleFinger", "RingFinger", "LittleFinger")]
            if any(b is None for b in knuckles):
                continue
            palm_local = (np.mean([b.head_local for b in knuckles], axis=0) + np.array(wrist.tail_local)) * .5
            palm = np.array(rig.matrix_world @ Vector(palm_local))
            for grip in grips:
                candidates.append((np.linalg.norm(grip-palm), wrist, palm, grip))
        if not candidates:
            reports[obj.name] = {"passed": False, "reason": "missing grip hand or wrist landmarks"}
            continue
        gap, wrist, palm, grip = min(candidates, key=lambda item:item[0])
        tolerance = max(wrist.length * .001, 1e-7)
        if repair:
            if grip_marker is None:
                obj["grip_local"] = list(obj.matrix_world.inverted() @ Vector(grip))
            obj["grip_hand"] = "Left" if "Left" in wrist.name else "Right"
            if gap > tolerance:
                obj.matrix_world = Matrix.Translation(Vector(palm-grip)) @ obj.matrix_world
                bpy.context.view_layer.update()
            for group in list(obj.vertex_groups):
                if rig.data.bones.get(group.name):
                    obj.vertex_groups.remove(group)
            obj.vertex_groups.new(name=wrist.name).add(list(range(len(p))), 1., "REPLACE")
        group = obj.vertex_groups.get(wrist.name)
        rigid = group is not None and all(
            any(g.group == group.index and abs(g.weight-1.) < 1e-6 for g in v.groups)
            and not any(g.group != group.index and g.weight > 1e-6 and rig.data.bones.get(obj.vertex_groups[g.group].name) for g in v.groups)
            for v in obj.data.vertices)
        error = np.linalg.norm(np.array(obj.matrix_world @ Vector(obj["grip_local"]))-palm) if repair else gap
        reports[obj.name] = {"wrist": wrist.name, "rest_grip_gap": float(error),
                             "passed": bool(rigid and error <= tolerance)}
    return reports
