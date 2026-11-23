"""Detect and probe secondary deformation regions in a Pi rest-pose scene."""

import math
import re
from collections import defaultdict
from heapq import heappop, heappush

import bpy
import numpy as np
from mathutils import Vector


def positions(obj):
    local = np.empty(len(obj.data.vertices) * 3, dtype=np.float32)
    obj.data.vertices.foreach_get("co", local)
    transform = np.asarray(obj.matrix_world, dtype=float)
    return (
        np.einsum("ij,kj->ik", local.reshape(-1, 3), transform[:3, :3])
        + transform[:3, 3]
    )


def islands(obj, ids):
    remaining = set(map(int, ids))
    neighbors = defaultdict(list)
    welded = {}
    for i in remaining:
        key = tuple(round(x, 6) for x in obj.data.vertices[i].co)
        j = welded.setdefault(key, i)
        if i != j:
            neighbors[i].append(j)
            neighbors[j].append(i)
    for edge in obj.data.edges:
        a, b = edge.vertices
        if a in remaining and b in remaining:
            neighbors[a].append(b)
            neighbors[b].append(a)
    while remaining:
        stack = [remaining.pop()]
        component = []
        while stack:
            i = stack.pop()
            component.append(i)
            for j in neighbors[i]:
                if j in remaining:
                    remaining.remove(j)
                    stack.append(j)
        yield np.array(sorted(component)), neighbors


def semantic(name):
    name = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
    for kind, pattern in [
        ("wing", r"(?<![a-z])wings?(?![a-z])|翅膀|羽翼"),
        ("hair", r"hair|bangs|ponytail|頭髪|头发"),
        ("tail", r"(?<![a-z])tails?(?![a-z])|尾巴|しっぽ"),
    ]:
        if re.search(pattern, name, re.I):
            return kind
    return None


def inventory(rig, spec, unresolved=None):
    def joint(name):
        return np.array(rig.matrix_world @ rig.data.bones[name].head_local)

    hips, chest, head = map(joint, ("DEF-Hips", "DEF-Chest", "DEF-Head"))
    scale = np.linalg.norm(head - hips)
    front = np.asarray(spec["front"], dtype=float)
    if (
        not np.isfinite(scale)
        or scale <= 0
        or front.shape != (3,)
        or np.linalg.norm(front[:2]) < 1e-6
    ):
        raise ValueError("无法从骨架与角色朝向建立识别坐标")
    front[2] = 0
    front /= np.linalg.norm(front)
    side = np.cross([0.0, 0.0, 1.0], front)
    regions = []
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH" or obj.find_armature() != rig:
            continue
        p = positions(obj)
        batches = defaultdict(set)
        for face in obj.data.polygons:
            slots = obj.material_slots
            material = (
                slots[face.material_index].name
                if face.material_index < len(slots)
                else ""
            )
            hint = semantic(material) or (
                "hair" if obj.name == spec.get("hair") else semantic(obj.name)
            )
            batches[hint, material].update(face.vertices)
        for (hint, material), vertices in batches.items():
            shell = p[sorted(vertices)]
            # Material islands remain available after joining objects. Infer a
            # shared cap only when the whole material sits behind/above the skull.
            if (
                not hint
                and obj.name != spec.get("head")
                and len(batches) > 1
                and np.quantile(shell[:, 2], 0.05) > head[2] - 0.15 * scale
                and np.quantile(shell[:, 2], 0.90) > head[2] + 0.32 * scale
                and np.quantile(-np.sum((shell - chest) * front, axis=1), 0.85)
                > 0.20 * scale
            ):
                hint = "hair"
            for ids, graph in islands(obj, vertices):
                if len(ids) < 4:
                    continue
                q = p[ids]
                lateral = np.sum((q - chest) * side, axis=1)
                back = -np.sum((q - chest) * front, axis=1)
                height = q[:, 2]
                # Classify projecting shells by attachment and shape in the rig frame.
                # For welded meshes, grow only protruding regions beyond the trunk.
                masks = []
                if hint:
                    masks.append((hint, np.ones(len(q), dtype=bool)))
                else:
                    med = np.median(q, axis=0)
                    span = np.ptp(q, axis=0)
                    near_head = np.linalg.norm(med - head) < scale * 0.65
                    if (
                        obj.name != spec.get("head")
                        and near_head
                        and np.quantile(height, 0.1) > head[2] - 0.25 * scale
                        and np.quantile(back, 0.8) > 0.18 * scale
                        and np.max(span) > 0.20 * scale
                    ):
                        masks.append(("hair", np.ones(len(q), dtype=bool)))
                    elif (
                        np.median(back) > 0.15 * scale
                        and np.median(height) > chest[2]
                        and min(abs(lateral.min()), abs(lateral.max())) > 0.12 * scale
                        and np.ptp(lateral) > 0.5 * scale
                        and np.ptp(height) < 1.6 * np.ptp(lateral)
                    ):
                        masks.append(("wing", np.ones(len(q), dtype=bool)))
                    elif (
                        not any(" arm" in b.name.lower() for b in rig.data.bones)
                        and min(-lateral.min(), lateral.max()) > scale * 0.85
                        and np.ptp(lateral) > 2 * np.ptp(height)
                    ):
                        # A transverse pair on one continuous body. Estimate the
                        # trunk half-width from the central half of its surface.
                        trunk = max(scale * 0.12, np.quantile(abs(lateral), 0.48))
                        rear = -np.sum((q - hips) * front, axis=1)
                        tail = (rear > scale * 0.42) & (abs(lateral) < trunk * 1.4)
                        if np.max(rear[tail], initial=0) > scale * 0.9:
                            masks.append(("tail", tail))
                        else:
                            tail[:] = False
                        masks.append(("wing", (abs(lateral) > trunk) & ~tail))
                    elif (
                        np.linalg.norm(med - hips) < scale * 0.85
                        and np.median(back) > 0.22 * scale
                        and np.ptp(lateral) > 0.35 * scale
                        and np.ptp(height) < scale * 0.72
                    ):
                        masks.append(("tail", np.ones(len(q), dtype=bool)))
                    else:
                        # Posterior proposals exclude ordinary frontal limbs.
                        wing = (
                            (back > 0.30 * scale)
                            & (height > chest[2] - 0.12 * scale)
                            & (abs(lateral) > 0.25 * scale)
                        )
                        if np.max(abs(lateral[wing]), initial=0) > 0.65 * scale:
                            masks.append(("wing", wing))
                        tail = (back > 0.34 * scale) & (
                            height < chest[2] - 0.12 * scale
                        )
                        if np.max(back[tail], initial=0) > 0.55 * scale:
                            masks.append(("tail", tail))
                        hair = (back > 0.26 * scale) & (height > head[2] - 0.12 * scale)
                        if np.max(back[hair], initial=0) > 0.40 * scale:
                            masks.append(("hair", hair))
                # Flag a large unaccounted posterior projection on the body.
                # Use distance to the primary skeleton to exclude a posed arm.
                if unresolved is not None and obj.name in {spec.get("body"), "body"}:
                    covered = np.zeros(len(q), dtype=bool)
                    for _, mask in masks:
                        covered |= mask
                    rear_trunk = max(0.0, float(np.dot(chest - hips, front)))
                    candidate = (
                        (~covered)
                        & (back > rear_trunk + 0.32 * scale)
                        & (height > hips[2] - 0.45 * scale)
                    )
                    if np.count_nonzero(candidate) >= 4:
                        points = q[candidate]
                        nearest = np.full(len(points), np.inf)
                        for bone in rig.data.bones:
                            if not bone.name.startswith("DEF-"):
                                continue
                            a = np.asarray(rig.matrix_world @ bone.head_local)
                            b = np.asarray(rig.matrix_world @ bone.tail_local)
                            axis = b - a
                            t = np.clip(
                                np.sum((points - a) * axis, axis=1)
                                / max(np.dot(axis, axis), 1e-12),
                                0,
                                1,
                            )
                            nearest = np.minimum(
                                nearest,
                                np.linalg.norm(points - a - t[:, None] * axis, axis=1),
                            )
                        if np.count_nonzero(nearest > 0.32 * scale) >= 4:
                            unresolved.append(
                                dict(
                                    object=obj.name,
                                    kind="unresolved",
                                    passed=False,
                                    bounds=[
                                        points[nearest > 0.32 * scale].min(0).tolist(),
                                        points[nearest > 0.32 * scale].max(0).tolist(),
                                    ],
                                    vertices=int(
                                        np.count_nonzero(nearest > 0.32 * scale)
                                    ),
                                    reason="unclassified posterior protrusion",
                                )
                            )
                for kind, mask in masks:
                    parent = {
                        "wing": "DEF-Chest",
                        "tail": "DEF-Hips",
                        "hair": "DEF-Head",
                    }[kind]
                    anchor = joint(parent)
                    groups = [mask]
                    if kind == "wing":
                        groups = [mask & (lateral >= 0), mask & (lateral < 0)]
                    elif (
                        kind == "hair"
                        and len(ids) > 90
                        and np.ptp(lateral[mask]) > 0.16 * scale
                    ):
                        # Split broad caps into sectors, leaving the crown pinned.
                        center = np.median(q[mask], axis=0)
                        angle = np.arctan2(
                            np.sum((q - center) * side, axis=1),
                            np.sum((q - center) * front, axis=1),
                        )
                        sector = (
                            np.floor((angle + math.pi) * 6 / (2 * math.pi)).astype(int)
                            % 6
                        )
                        groups = [mask & (sector == j) for j in range(6)]
                    for group in groups:
                        if np.count_nonzero(group) < 4:
                            continue
                        ix = ids[group]
                        if kind == "hair":
                            root = ix[np.argmax(p[ix, 2])]
                        else:
                            root = ix[np.argmin(np.linalg.norm(p[ix] - anchor, axis=1))]
                        # Compute distance over actual mesh edges (including UV seams).
                        allowed = set(map(int, ix))
                        dist = {int(root): 0.0}
                        queue = [(0.0, int(root))]
                        while queue:
                            value, i = heappop(queue)
                            if value != dist[i]:
                                continue
                            for j in graph[i]:
                                if j not in allowed:
                                    continue
                                cost = value + np.linalg.norm(p[i] - p[j])
                                if cost < dist.get(j, float("inf")):
                                    dist[j] = cost
                                    heappush(queue, (cost, j))
                        # Disconnected sector slices still receive an anatomical coordinate.
                        d = np.array(
                            [
                                dist.get(int(i), np.linalg.norm(p[i] - p[root]))
                                for i in ix
                            ]
                        )
                        if kind == "hair":
                            d = p[root, 2] - p[ix, 2]
                        if np.max(d) < scale * 0.02:
                            continue
                        u = np.clip(d / max(np.quantile(d, 0.98), 1e-12), 0, 1)
                        regions.append((obj, kind, parent, ix, u))
    return regions


def probe(rig, region, regions, at_root=False):
    obj, kind, parent, ids, u = region
    distal = ids[u >= 0.83]
    names = defaultdict(float)
    for i in distal:
        for g in obj.data.vertices[int(i)].groups:
            name = obj.vertex_groups[g.group].name
            bone = rig.data.bones.get(name)
            if (
                bone
                and (bone.get("studio_spring") == kind or semantic(name) == kind)
                and parent in [b.name for b in bone.parent_recursive]
            ):
                names[name] += g.weight
    if not names:
        return {"passed": False, "reason": "free end has no matching deform bone"}
    name = max(names, key=names.get)
    bone = rig.pose.bones[name]
    if at_root:
        while bone.parent and bone.parent.name != parent:
            bone = bone.parent
    deps = bpy.context.evaluated_depsgraph_get()
    before = positions(obj.evaluated_get(deps))
    neighbors = [other for other in regions if other is not region]
    samples = {}
    for other, _, _, indices, coordinate in neighbors:
        samples.setdefault(other.name, []).extend(indices[coordinate >= 0.83])
    on_object = [other[3] for other in regions if other[0] == obj]
    protected = np.setdiff1d(np.arange(len(before)), np.concatenate(on_object))
    baseline = {
        key: positions(bpy.data.objects[key].evaluated_get(deps))[ix]
        for key, ix in samples.items()
    }
    basis = bone.matrix_basis.copy()
    try:
        from mathutils import Matrix

        bone.matrix_basis = basis @ Matrix.Rotation(0.25, 4, "X")
        bpy.context.view_layer.update()
        delta = np.linalg.norm(positions(obj.evaluated_get(deps)) - before, axis=1)
        displaced = {
            key: np.linalg.norm(
                positions(bpy.data.objects[key].evaluated_get(deps))[ix]
                - baseline[key],
                axis=1,
            )
            for key, ix in samples.items()
        }
        neighbor_peak = max(
            (float(np.max(a)) for a in displaced.values() if len(a)), default=0.0
        )
    finally:
        bone.matrix_basis = basis
        bpy.context.view_layer.update()
    length = max(np.ptp(before[ids], axis=0))
    body_peak = float(np.max(delta[protected], initial=0.0))
    tip = float(np.median(delta[distal]))
    root = float(np.median(delta[ids[u <= 0.10]])) if np.any(u <= 0.10) else 0.0
    result = dict(
        passed=bool(
            tip > length * 0.001
            and root < max(length * 0.002, tip * 0.2)
            and neighbor_peak < max(length * 0.002, tip * 0.4)
            and body_peak < max(length * 0.002, tip * 0.2)
        ),
        bone=bone.name,
        neighbor_peak=neighbor_peak,
        protected_peak=body_peak,
        tip_displacement=tip,
        root_displacement=root,
    )
    if not at_root and kind in ("wing", "tail") and result["passed"]:
        result["root_probe"] = probe(rig, region, regions, at_root=True)
        result["passed"] = result["root_probe"]["passed"]
    return result


def fit(rig, region):
    obj, kind, parent, ids, u = region
    p = positions(obj)[ids]
    count = min(5 if kind == "tail" else 3, max(1, len(ids) // 12))
    curve = []
    for t in np.linspace(0, 1, count + 1):
        close = np.argsort(abs(u - t))[: max(1, len(ids) // 18)]
        curve.append(np.median(p[close], axis=0))
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    names = []
    inv = rig.matrix_world.inverted()
    try:
        for a, b in zip(curve, curve[1:]):
            if np.linalg.norm(a - b) < 1e-8:
                continue
            bone = rig.data.edit_bones.new(kind.title() + ".Section")
            bone.head = inv @ Vector(a)
            bone.tail = inv @ Vector(b)
            bone.parent = rig.data.edit_bones[names[-1] if names else parent]
            bone.use_connect = bool(names)
            names.append(bone.name)
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
    if not names:
        raise ValueError("Collapsed appendage guide: " + obj.name)
    groups = []
    for name in [parent] + names:
        groups.append(obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name))
    for i, t in zip(ids, u):
        i = int(i)
        for group_id in [g.group for g in obj.data.vertices[i].groups]:
            if rig.data.bones.get(obj.vertex_groups[group_id].name):
                obj.vertex_groups[group_id].remove([i])
        x = float(t) * len(names)
        lo = int(x)
        groups[lo].add([i], 1 - (x - lo), "REPLACE")
        if x > lo:
            groups[lo + 1].add([i], x - lo, "REPLACE")
    for name in names:
        set_dynamics(rig.data.bones[name], kind)
    bpy.context.view_layer.update()
    return names


def set_dynamics(bone, kind):
    bone["studio_spring"] = kind
    for key, default in [
        ("frequency_hz", 3.8 if kind == "hair" else 2.6),
        ("damping_ratio", 0.8),
        ("angular_limit_deg", 12.0 if kind == "hair" else 19.0),
    ]:
        if key not in bone:
            bone[key] = default


def check(rig, spec, repair=False):
    unbound = []
    targets = set(spec.get("parts", [])) | {
        spec.get("hair"),
        spec.get("body"),
        spec.get("head"),
    }
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH" or obj.find_armature() == rig:
            continue
        expected = (
            "hair" if obj.name == spec.get("hair") else semantic(obj.name)
        ) or next(
            (semantic(s.name) for s in obj.material_slots if semantic(s.name)), None
        )
        if obj.name not in targets and not expected:
            continue
        if repair and expected and obj.find_armature() is None:
            modifier = obj.modifiers.new("Secondary deformation", "ARMATURE")
            modifier.object = rig
        else:
            unbound.append(
                dict(
                    object=obj.name,
                    kind=expected,
                    passed=False,
                    reason="mesh missing expected armature",
                )
            )
    regions = inventory(rig, spec, unbound)
    records = []
    for region in regions:
        obj, kind, parent, ids, u = region
        before = probe(rig, region, regions)
        names = fit(rig, region) if repair and not before["passed"] else []
        records.append(
            dict(
                object=obj.name,
                kind=kind,
                vertices=len(ids),
                before=before,
                added=names,
            )
        )
    for record, region in zip(records, regions):
        record.update(probe(rig, region, regions))
        if repair and record["passed"]:
            bone = rig.data.bones[record["bone"]]
            while (
                bone
                and bone.name != region[2]
                and (
                    semantic(bone.name) == region[1]
                    or bone.get("studio_spring") == region[1]
                )
            ):
                set_dynamics(bone, region[1])
                bone = bone.parent
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH" or obj.find_armature() != rig:
            continue
        expected = {semantic(slot.name) for slot in obj.material_slots} | {
            semantic(obj.name)
        }
        for kind in expected - {None}:
            if not any(r["object"] == obj.name and r["kind"] == kind for r in records):
                records.append(
                    dict(
                        object=obj.name,
                        kind=kind,
                        passed=False,
                        reason="identified part lacks a testable free end",
                    )
                )
    for name in [spec.get("hair")]:
        if name and not any(
            r["object"] == name and r["kind"] == "hair" for r in records
        ):
            records.append(
                dict(
                    object=name,
                    kind="hair",
                    passed=False,
                    reason="expected hair missing",
                )
            )
    records.extend(unbound)
    return dict(version=2, passed=all(r["passed"] for r in records), regions=records)
