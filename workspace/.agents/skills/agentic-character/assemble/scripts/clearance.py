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


def fit(base, tris, fixed, gap, budget, iterations):
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
    for iteration in range(iterations+1):
        pairs = fixed.overlap(tree(points, faces))
        history.append(len(pairs))
        score = (len(pairs), float(np.sum((points-start)**2)))
        if score < best_score:
            best_score = score
            best = points.copy()
        if not pairs or iteration == iterations:
            break
        region = faces[np.unique([j for _,j in pairs])]
        active = np.unique(region)
        shift = np.zeros_like(points)
        weight = np.zeros(len(points))
        def accumulate(samples, indices, multiplicity):
            corrections = np.zeros_like(samples)
            for i, position in enumerate(samples):
                hit, normal, _, _ = fixed.find_nearest(position)
                if hit is None:
                    continue
                n = np.asarray(normal)
                amount = gap - np.dot(position-np.asarray(hit), n)
                if amount > 0:
                    corrections[i] = min(amount,budget*.35)*n
            used = np.any(corrections != 0, axis=1)
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
    return base+(best-start)[shared],history


