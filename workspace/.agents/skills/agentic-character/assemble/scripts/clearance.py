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
    for iteration in range(iterations+1):
        pairs = fixed.overlap(tree(points, faces))
        history.append(len(pairs))
        if len(pairs) <= min(history):
            best = points.copy()
        if not pairs or iteration == iterations:
            break
        region = faces[np.unique([j for _,j in pairs])]
        active = np.unique(region)
        shift = np.zeros_like(points)
        weight = np.zeros(len(points))
        def constraint(position, indices):
            hit, normal, _, _ = fixed.find_nearest(position)
            if hit is None:
                return
            n = np.asarray(normal)
            amount = gap - np.dot(position-np.asarray(hit),n)
            if amount > 0:
                shift[indices] += min(amount,budget*.35)*n
                weight[indices] += 1
        for i in active:
            constraint(points[i], [i])
        for tri in region:
            constraint(points[tri].mean(0),tri)
            for a,b in zip(tri,np.roll(tri,1)):
                constraint((points[a]+points[b])*.5,[a,b])
        shift /= np.maximum(weight,1)[:,None]
        # Carry local offsets into the immediate neighbours to soften the boundary.
        nearby=np.zeros_like(points)
        np.add.at(nearby,left,shift[right])
        shift=.8*shift+.35*nearby/degree[:,None]
        offset=points+shift-start
        points=start+offset*np.minimum(1,budget/np.maximum(np.linalg.norm(offset,axis=1),1e-12))[:,None]
    return base+(best-start)[shared],history


