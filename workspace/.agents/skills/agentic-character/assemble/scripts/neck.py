"""Fit a static head rim to an oval cut in an upward-facing body cap."""

import math
from collections import Counter
import bmesh
from neck_open import fit_open_neck
from mathutils import Vector


def fit_closed_neck(bo, h, options):
    def key(p):
        return tuple(round(x, 6) for x in p)

    def edge(a, b):
        return tuple(sorted((a, b)))

    def worldbm(o):
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bm.transform(o.matrix_world)
        return bm

    def savebm(bm, o):
        bm.transform(o.matrix_world.inverted())
        bm.to_mesh(o.data)
        bm.free()
        o.data.update()

    def geometry(fs):
        return (
            list(set(v for f in fs for v in f.verts))
            + list(set(e for f in fs for e in f.edges))
            + fs
        )

    # Clip an oval only against the top (upward-facing) triangles. Their
    # interpolated surface remains exactly the original body outside the opening.
    bm = worldbm(bo)
    bm.normal_update()
    cx, cy = options["center_xy"]
    rx, ry = options["radii"]
    floor = options["min_body_z"]
    faces = [
        f
        for f in bm.faces
        if f.normal.z > 0
        and min(v.co.z for v in f.verts) > floor
        and min(v.co.x for v in f.verts) <= cx + rx
        and max(v.co.x for v in f.verts) >= cx - rx
        and min(v.co.y for v in f.verts) <= cy + ry
        and max(v.co.y for v in f.verts) >= cy - ry
    ]
    for j in range(24):
        t = (j + 0.5) * math.tau / 24
        norm = Vector((math.cos(t) / rx, math.sin(t) / ry, 0)).normalized()
        pt = Vector(
            (
                cx + rx * math.cos(j * math.tau / 24),
                cy + ry * math.sin(j * math.tau / 24),
                0,
            )
        )
        r = bmesh.ops.bisect_plane(
            bm, geom=geometry(faces), plane_co=pt, plane_no=norm, dist=1e-8
        )
        faces = list(
            {
                f
                for f in faces + r["geom"]
                if isinstance(f, bmesh.types.BMFace)
                and f.is_valid
                and (f.calc_center_median() - pt).dot(norm) < 1e-8
            }
        )
    bmesh.ops.delete(bm, geom=faces, context="FACES")

    def angle(p):
        return math.atan2((p.y - cy) / ry, (p.x - cx) / rx) % math.tau

    def onoval(p):
        return (
            abs(
                max(
                    math.cos((i + 0.5) * math.tau / 24) * (p.x - cx) / rx
                    + math.sin((i + 0.5) * math.tau / 24) * (p.y - cy) / ry
                    for i in range(24)
                )
                - math.cos(math.pi / 24)
            )
            < 2e-4
        )

    edges = [
        e
        for e in bm.edges
        if e.is_boundary and all(v.co.z > floor and onoval(v.co) for v in e.verts)
    ]
    bodysegments = [(e.verts[0].co.copy(), e.verts[1].co.copy()) for e in edges]

    def loopcheck(segments):
        c = Counter(key(p) for e in segments for p in e)
        if not c or set(c.values()) != {2}:
            raise ValueError(
                "Expected a closed perimeter at the specified neck landmarks"
            )

    loopcheck(bodysegments)
    B = sorted({key(p): p for e in bodysegments for p in e}.values(), key=angle)
    assert all(
        edge(key(p), key(q)) in {edge(key(a), key(b)) for a, b in bodysegments}
        for p, q in zip(B, B[1:] + B[:1])
    )
    savebm(bm, bo)
    hm = worldbm(h)
    cut = options["head_cut_z"]
    r = bmesh.ops.bisect_plane(
        hm,
        geom=list(hm.verts) + list(hm.edges) + list(hm.faces),
        plane_co=(0, 0, cut),
        plane_no=(0, 0, 1),
        clear_inner=True,
        dist=1e-8,
    )
    he = [
        e
        for e in hm.edges
        if e.is_boundary and all(abs(v.co.z - cut) < 1e-6 for v in e.verts)
    ]
    loopcheck([(e.verts[0].co, e.verts[1].co) for e in he])
    H = {key(v.co): v.co.copy() for e in he for v in e.verts}
    hc = sum(H.values(), Vector()) / len(H)
    ordered = sorted(H.values(), key=lambda p: math.atan2(p.y - hc.y, p.x - hc.x))
    source_edges = {edge(key(e.verts[0].co), key(e.verts[1].co)) for e in he}
    if any(
        edge(key(a), key(b)) not in source_edges
        for a, b in zip(ordered, ordered[1:] + ordered[:1])
    ):
        raise ValueError("Head cut must produce one star-shaped perimeter")

    def ha(p):
        return math.atan2(p.y - hc.y, p.x - hc.x) % math.tau

    def frac(a, b, t):
        return ((t - a) % math.tau) / ((b - a) % math.tau)

    def nearest_angle(t):
        return min(B, key=lambda p: abs((angle(p) - t + math.pi) % math.tau - math.pi))

    def lookup(t):
        p = nearest_angle(t)
        if abs((angle(p) - t + math.pi) % math.tau - math.pi) < 1e-7:
            return p.copy()
        for a, b in zip(B, B[1:] + B[:1]):
            f = frac(angle(a), angle(b), t)
            if f < 1:
                return a.lerp(b, f)
        raise RuntimeError(t)

    # Split head edges at every body boundary corner. Each interval then
    # lies on exactly one straight body edge.
    targets = {}
    for e in he:
        a, b = e.verts
        if (ha(b.co) - ha(a.co)) % math.tau > math.pi:
            a, b = b, a
        start, end = ha(a.co), ha(b.co)
        targets[a] = lookup(start)
        targets[b] = lookup(end)
        last = 0
        for f, p in sorted(
            [
                (frac(start, end, angle(p)), p)
                for p in B
                if 1e-7 < frac(start, end, angle(p)) < 1 - 1e-7
            ],
            key=lambda pair: pair[0],
        ):
            _, a = bmesh.utils.edge_split(e, a, (f - last) / (1 - last))
            targets[a] = p.copy()
            e = hm.edges.get((a, b))
            last = f
    for v in hm.verts:
        if v in targets:
            continue
        if cut < v.co.z < cut + options["blend_height"]:
            t = ha(v.co)
            ref = min(
                H.values(),
                key=lambda p: abs((ha(p) - t + math.pi) % math.tau - math.pi),
            )
            w = 1 - (v.co.z - cut) / options["blend_height"]
            v.co += (lookup(ha(ref)) - ref) * w * w
    for v, p in targets.items():
        v.co = p
    hs = [
        (e.verts[0].co.copy(), e.verts[1].co.copy())
        for e in hm.edges
        if e.is_boundary and all(v in targets for v in e.verts)
    ]
    loopcheck(hs)
    savebm(hm, h)

    def distance(p, a, b):
        d = b - a
        return (p - a - d * min(1, max(0, (p - a).dot(d) / d.length_squared))).length

    def gap(src, dst):
        return max(
            min(distance(a.lerp(b, t), c, d) for c, d in dst)
            for a, b in src
            for t in [0, 0.25, 0.5, 0.75, 1]
        )

    error = max(gap(hs, bodysegments), gap(bodysegments, hs))
    if error > 1e-6:
        raise ValueError(f"Neck boundary mismatch {error}")
    return {bo.name: bodysegments, h.name: hs}



def fit_neck(bo, h, options):
    open_error = None
    chin = options.get("chin_min_z")
    if chin is None or not math.isfinite(chin):
        raise ValueError("Measure chin_min_z on the placed head before fitting its neck")
    blend = options["blend_height"]
    original_cut = options["head_cut_z"]
    if not math.isfinite(blend) or blend <= 0 or not math.isfinite(original_cut):
        raise ValueError("Invalid neck transition band")
    if original_cut + blend >= chin:
        raise ValueError("Neck transition reaches the protected chin; lower the neck band")

    for offset in (0, 0.25, 0.5, -0.25, -0.5):
        candidate = dict(options, head_cut_z=original_cut + offset * options["blend_height"])
        if candidate["head_cut_z"] + blend >= chin:
            continue
        try:
            return fit_open_neck(bo, h, candidate)
        except ValueError as error:
            open_error = error
    try:
        return fit_closed_neck(bo, h, options)
    except (ValueError, AssertionError) as error:
        raise ValueError(f"Existing-rim fit: {open_error}. Closed-cap fit: {error}.") from error
