"""Blender entry point for auditing, upgrading, and reopening a Pi rig."""

import json
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from secondary_coverage import check
from handheld import check_handhelds


def armature(spec):
    if spec.get("body"):
        rig = bpy.context.scene.objects[spec["body"]].find_armature()
    else:
        rigs = [
            o
            for o in bpy.context.scene.objects
            if o.type == "ARMATURE" and "DEF-Chest" in o.data.bones
        ]
        rig = rigs[0] if len(rigs) == 1 else None
    if not rig:
        raise ValueError("无法确定需要复核的身体骨架")
    return rig


def upgrade(spec, output):
    result = check(armature(spec), spec, repair=True)
    held = check_handhelds(armature(spec), repair=True)
    result["handhelds"] = held
    invalid = {}
    rig = armature(spec)
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH" or obj.find_armature() != rig:
            continue
        deform = {
            g.index
            for g in obj.vertex_groups
            if rig.data.bones.get(g.name) and rig.data.bones[g.name].use_deform
        }
        errors = 0
        for v in obj.data.vertices:
            weights = [g.weight for g in v.groups if g.group in deform and g.weight > 0]
            if len(weights) > 4 or abs(sum(weights) - 1.0) > 1e-5:
                errors += 1
        if errors or any(m.type == "MASK" for m in obj.modifiers):
            invalid[obj.name] = {
                "invalid_vertices": errors,
                "mask": any(m.type == "MASK" for m in obj.modifiers),
            }
    result["invalid_skins"] = invalid
    result["passed"] = result["passed"] and not invalid and all(x["passed"] for x in held.values())
    if result["passed"]:
        bpy.context.preferences.filepaths.save_version = 0
        bpy.ops.wm.save_as_mainfile(filepath=str(output))
        bpy.ops.wm.open_mainfile(filepath=str(output))
        readback = check(armature(spec), spec)
        checked = check_handhelds(armature(spec))
        readback["passed"] = readback["passed"] and checked.keys() == held.keys() and all(x["passed"] for x in checked.values())
        result["readback_passed"] = readback["passed"]
        result["passed"] = readback["passed"]
    return result


if __name__ == "__main__":
    plan, folder = sys.argv[sys.argv.index("--") + 1 :]
    folder = Path(folder)
    report = upgrade(json.loads(plan), folder / "rig.blend")
    (folder / "stage-report.json").write_text(
        json.dumps({"passed": report["passed"], "secondaryCoverage": report}, indent=2)
    )
