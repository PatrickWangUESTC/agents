from bisect import bisect_right
from collections import Counter

import bmesh


def fit_open_neck(body, head, options):
    """Match an existing open body rim without cutting the surrounding body."""
    def key(p):
        return tuple(round(v, 6) for v in p)

    def edge(a, b):
        return tuple(sorted((key(a), key(b))))

    def mesh(obj):
        value = bmesh.new()
        value.from_mesh(obj.data)
        value.transform(obj.matrix_world)
        return value

    def ring(segments):
        points = {}
        neighbors = {}
        for a, b in segments:
            for point, other in ((a, b), (b, a)):
                token = key(point)
                points[token] = point.copy()
                neighbors.setdefault(token, set()).add(key(other))
        if len(points) < 6 or any(len(links) != 2 for links in neighbors.values()):
            raise ValueError('Expected one closed physical neck rim')
        anchor = max(points, key=lambda p: (p[0], -abs(p[1]), p[2]))
        order = [anchor]
        last, cursor = anchor, min(neighbors[anchor])
        while cursor != anchor and len(order) < len(points):
            order.append(cursor)
            following = next(iter(neighbors[cursor] - {last}))
            last, cursor = cursor, following
        if cursor != anchor or len(order) != len(points):
            raise ValueError('Multiple or disconnected neck rims')
        xyz = [points[p] for p in order]
        area = sum(a.x*b.y - a.y*b.x for a, b in zip(xyz, xyz[1:] + xyz[:1]))
        if area < 0:
            xyz[1:] = reversed(xyz[1:])
        length = [0.]
        for a, b in zip(xyz, xyz[1:] + xyz[:1]):
            length.append(length[-1]+(a-b).length)
        return xyz, [entry/length[-1] for entry in length]

    def opening_edges(bm):
        cx, cy = options['center_xy']
        rx, ry = options['radii']
        floor = options['min_body_z'] - options['blend_height']
        uses = Counter(edge(e.verts[0].co, e.verts[1].co) for e in bm.edges for _ in e.link_faces)
        return [
            e for e in bm.edges if uses[edge(e.verts[0].co, e.verts[1].co)] == 1
            and all(v.co.z > floor and abs(v.co.x-cx) < 1.5*rx and abs(v.co.y-cy) < 1.5*ry for v in e.verts)
        ]

    def coordinates(edges):
        return [(e.verts[0].co.copy(), e.verts[1].co.copy()) for e in edges]

    bm = mesh(body)
    try:
        body_points, body_arc = ring(coordinates(opening_edges(bm)))
    finally:
        bm.free()

    hm = mesh(head)
    try:
        cut = options['head_cut_z']
        bmesh.ops.bisect_plane(hm, geom=list(hm.verts)+list(hm.edges)+list(hm.faces),
            plane_co=(0,0,cut),plane_no=(0,0,1),dist=1e-8,clear_inner=True)
        he = [e for e in hm.edges if e.is_boundary and all(abs(v.co.z-cut)<1e-6 for v in e.verts)]
        head_points, head_arc = ring([(e.verts[0].co,e.verts[1].co) for e in he])
        head_parameter={key(point): t for point,t in zip(head_points,head_arc)}

        def lookup(t):
            t %= 1.
            k=bisect_right(body_arc,t)-1
            return body_points[k].lerp(body_points[(k+1)%len(body_points)],(t-body_arc[k])/(body_arc[k+1]-body_arc[k]))

        def split_at_arc(bm, edges, parameter, knots):
            targets = {}
            for e in edges:
                a, b = e.verts
                start, end = (parameter[key(v.co)] for v in (a, b))
                if (end-start) % 1. > .5:
                    a, b, start, end = b, a, end, start
                span = (end-start) % 1.
                targets[a], targets[b] = lookup(start), lookup(end)
                prev = 0.
                for f, t in sorted((((t-start) % 1.)/span, t) for t in knots if 1e-8 < (t-start) % 1. < span-1e-8):
                    _, a = bmesh.utils.edge_split(e, a, (f-prev)/(1-prev))
                    targets[a] = lookup(t)
                    e = bm.edges.get((a,b))
                    prev = f
            return targets

        targets = split_at_arc(hm, he, head_parameter, body_arc[:-1])
        displacements = [lookup(t)-p for p,t in zip(head_points,head_arc)]
        for v in hm.verts:
            if v in targets:continue
            h=v.co.z-cut
            if 0<h<options['blend_height']:
                index=min(range(len(head_points)),key=lambda i:(head_points[i]-v.co).length_squared)
                v.co += displacements[index]*(1-h/options['blend_height'])**2
        for v,p in targets.items():v.co=p
        head_segments = coordinates(
            e for e in hm.edges if e.is_boundary and all(v in targets for v in e.verts))
        ring(head_segments)
        bm = mesh(body)
        try:
            body_parameter = {key(p):t for p,t in zip(body_points,body_arc)}
            body_targets = split_at_arc(bm, opening_edges(bm), body_parameter, head_arc[:-1])
            for vertex,position in body_targets.items():
                vertex.co = position
            body_segments = coordinates(
                e for e in bm.edges if e.is_boundary and all(v in body_targets for v in e.verts))
            ring(body_segments)
            if len(body_segments) != len(head_segments) or {edge(a,b) for a,b in body_segments} != {edge(a,b) for a,b in head_segments}:
                raise ValueError(f'Open neck edge correspondence failed ({len(body_segments)}, {len(head_segments)})')
            for working, obj in ((bm,body),(hm,head)):
                working.transform(obj.matrix_world.inverted())
                working.to_mesh(obj.data)
                obj.data.update()
            return {body.name:body_segments,head.name:head_segments}
        finally:
            bm.free()
    finally:
        hm.free()
