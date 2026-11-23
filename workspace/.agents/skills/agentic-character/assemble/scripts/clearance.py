"""Bounded local contact solver used by refine_contacts.py.

Correct local intersections against the fixed body on a copy. Distances in
settings are fractions of the fixed body's world-space height.
"""
import numpy as np
from mathutils.bvhtree import BVHTree


def surface(obj):
    obj.data.calc_loop_triangles()
    points = np.asarray([obj.matrix_world @ v.co for v in obj.data.vertices])
    triangles = np.array([tuple(f.vertices) for f in obj.data.loop_triangles])
    return points, triangles


def tree(points, faces):
    return BVHTree.FromPolygons(points.tolist(), faces.tolist(), all_triangles=True)


def fit(base, tris, fixed, gap, budget, iterations, mobility=None):
    # Tie coincident UV-split vertices without welding the delivered mesh.
    _, first, shared = np.unique(np.round(base, 7), axis=0, return_index=True, return_inverse=True)
    start = base[first]
    points = start.copy()
    faces = shared[tris]
    edges = np.unique(np.sort(np.c_[faces.ravel(),np.roll(faces,1,axis=1).ravel()],axis=1),axis=0)
    left,right = np.r_[edges[:,0],edges[:,1]],np.r_[edges[:,1],edges[:,0]]
    degree = np.bincount(left,minlength=len(points)).clip(1)
    best = points.copy()
    history = []
    best_score = (float("inf"), float("inf"))
    factors = None if mobility is None else np.asarray(mobility, dtype=float)
    if factors is not None and (factors.shape != (len(base),) or
                                not np.isfinite(factors).all() or np.any((factors < 0) | (factors > 1))):
        raise ValueError("Expected one mobility factor in [0, 1] per source vertex")
    # Rank the geometry that will actually be applied, including frozen regions.
    # Keep the original proposal sequence so every former candidate is still available.
    for iteration in range(iterations+1):
        pairs = fixed.overlap(tree(points, faces))
        history.append(len(pairs))
        offset = points-start
        applied_offset = offset if factors is None else offset[shared]*factors[:,None]
        applied_count = len(pairs) if factors is None else len(fixed.overlap(tree(base+applied_offset, tris)))
        score = (applied_count, float(np.sum(applied_offset**2)))
        if score < best_score:
            best_score = score
            best = points.copy()
        if not pairs or not applied_count or iteration == iterations:
            break
        region = faces[np.unique([j for _,j in pairs])]
        active = np.unique(region)
        shift = np.zeros_like(points)
        weight = np.zeros(len(points))
        def accumulate(samples, indices, multiplicity):
            hits = [fixed.find_nearest(point) for point in samples]
            if not hits or hits[0][0] is None:
                return  # empty collider
            origins = np.asarray([tuple(hit) for hit, _, _, _ in hits])
            normals = np.asarray([tuple(normal) for _, normal, _, _ in hits])
            amounts = gap - np.einsum('ij,ij->i', samples-origins, normals)
            used = amounts > 0
            corrections = normals * np.minimum(amounts, budget*.35)[:,None]
            for column in indices.T:
                np.add.at(shift, column[used], corrections[used]*multiplicity[used,None])
                np.add.at(weight, column[used], multiplicity[used])

        accumulate(points[active], active[:,None], np.ones(len(active)))
        accumulate(points[region].mean(axis=1), region, np.ones(len(region)))
        # Adjacent triangles share a midpoint. Query it once and retain both contributions.
        sides = np.stack((region, np.roll(region, -1, axis=1)), axis=-1).reshape(-1,2)
        sides, counts = np.unique(np.sort(sides, axis=1), axis=0, return_counts=True)
        accumulate(points[sides].mean(axis=1), sides, counts)
        shift /= np.maximum(weight,1)[:,None]
        # Carry local offsets into the immediate neighbours to soften the boundary.
        nearby=np.zeros_like(points)
        np.add.at(nearby,left,shift[right])
        shift=.8*shift+.35*nearby/degree[:,None]
        offset=points+shift-start
        updated=start+offset*np.minimum(1,budget/np.maximum(np.linalg.norm(offset,axis=1),1e-12))[:,None]
        if np.array_equal(updated, points):
            break
        points = updated
    delta = (best-start)[shared]
    if factors is not None:
        delta *= factors[:,None]
    return base+delta,history


