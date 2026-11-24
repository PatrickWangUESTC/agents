"""Audit a topology-identified, arm-independent garment panel in Blender."""


def check_panel_arm_weights(garment, panel_vertices, *, arm_roots=None, tolerance=1e-7):
    """Return all leaking vertices. The panel excludes sleeves and shoulder transitions."""
    import math
    from operator import index

    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("Expected a finite nonnegative weight tolerance")
    rig = garment.find_armature()
    if rig is None:
        raise ValueError(f"{garment.name}: missing armature")
    bones = rig.data.bones
    roots = set(arm_roots if arm_roots is not None else
                ("DEF-Left arm", "DEF-Right arm"))
    if not roots or roots.difference(bones.keys()):
        raise ValueError(f"{garment.name}: verify the arm root names for this skeleton")
    forbidden = {bone.name for bone in bones if bone.use_deform and
                 (bone.name in roots or any(parent.name in roots for parent in bone.parent_recursive))}
    vertices = sorted(set(index(i) for i in panel_vertices))
    if not vertices or vertices[0] < 0 or vertices[-1] >= len(garment.data.vertices):
        raise ValueError(f"{garment.name}: missing or invalid panel region")
    groups = {g.index: g.name for g in garment.vertex_groups if g.name in forbidden}
    leaks = []
    for i in vertices:
        weights = {groups[g.group]: g.weight for g in garment.data.vertices[i].groups
                   if g.group in groups and g.weight > 0}
        total = sum(weights.values())
        if total > tolerance:
            leaks.append(dict(vertex=i, total=total, weights=weights))
    return dict(passed=not leaks, object=garment.name, checked=len(vertices), leaks=leaks)
