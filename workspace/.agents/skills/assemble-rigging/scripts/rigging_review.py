"""Geometry checks on world-space vertices from a single posed scene evaluation."""
import numpy as np
from mathutils.bvhtree import BVHTree


class CollisionRegion:
    """Fixed topology. Preserve face order so overlap indices identify the original faces."""

    def __init__(self, faces):
        faces = np.asarray(faces)
        if faces.ndim != 2 or faces.shape[1] != 3:
            raise ValueError("Expected triangles")
        self.vertices, local = np.unique(faces, return_inverse=True)
        self.faces = local.reshape(faces.shape).tolist()

    def tree(self, posed):
        return BVHTree.FromPolygons(posed[self.vertices].tolist(), self.faces, all_triangles=True)


class SkirtLengths:
    def __init__(self, vertices, rest, edges, paths, min_edge_length):
        """Use case-defined material vertices, seam mapping, paths and edge filter.

        vertices indexes the evaluated mesh. rest, edges and paths use the same
        material-point ordering. rest and posed coordinates must share units.
        """
        self.vertices = np.asarray(vertices, dtype=np.intp)
        lengths = np.linalg.norm(rest[edges[:, 0]] - rest[edges[:, 1]], axis=1)
        valid = lengths > min_edge_length
        self.left, self.right = edges[valid].T
        self.edges = lengths[valid]
        self.paths = list(paths)
        self.rest = self.path_lengths(rest)
        if not np.any(valid) or np.any(self.rest <= 0):
            raise ValueError("Empty edge sample or invalid material path")

    def path_lengths(self, points):
        return np.array([np.linalg.norm(np.diff(points[path], axis=0), axis=1).sum()
                         for path in self.paths])

    def measure(self, posed):
        points = posed[self.vertices]
        ratios = np.linalg.norm(points[self.left] - points[self.right], axis=1) / self.edges
        return np.quantile(ratios, [0, .01, .99, 1]), self.path_lengths(points) / self.rest
