"""Fit paired shells in body-aligned coordinates (depth, lateral, height)."""
from concurrent.futures import ThreadPoolExecutor

import numpy as np


def section(points, triangles, height):
    start = points[triangles]
    end = np.roll(start, -1, axis=1)
    crosses = (start[:, :, 2] > height) != (end[:, :, 2] > height)
    start, end = start[crosses], end[crosses]
    return start + (end - start) * ((height - start[:, 2]) / (end[:, 2] - start[:, 2]))[:, None]


def fit_pair(body, body_faces, shoes, shoe_faces, *, midline, ankle, levels, margin, max_scale, parallel=False):
    """Translate the lower shoe rigidly, then measure and fit each shaft by height.

    Inputs are corresponding Nx3 physical coordinates in the same pose.
    levels span the occupied shaft. A shoe already has its sole at floor height.
    midline separates the two standing feet and shells.
    """
    levels = np.asarray(levels, dtype=float)
    if levels.ndim != 1 or len(levels) < 2 or np.any(np.diff(levels) <= 0):
        raise ValueError("Expected increasing shaft sampling heights")
    if margin < 0 or max_scale < 1 or ankle >= levels[-1]:
        raise ValueError("Invalid shoe clearance, scale bound or ankle height")
    result = shoes.copy()
    if np.any(np.ptp(np.sign(shoes[shoe_faces, 1] - midline), axis=1) > 0):
        raise ValueError("Separate overlapping or midline-crossing shoe shells by identity first")
    def sided_sections(points, faces, side):
        # Retain triangles crossing the midline; filter the actual intersections below.
        faces = faces[np.any((points[faces, 1] - midline) * side > 0, axis=1)]
        heights = points[faces, 2]
        low, high = heights.min(axis=1), heights.max(axis=1)
        def at(z):
            active = faces[(low <= z) & (high > z)]
            samples = section(points, active, z)
            return samples[(samples[:, 1] - midline) * side > 0]
        return at

    def fit_side(side):
        ids = np.flatnonzero((shoes[:, 1] - midline) * side > 0)
        foot = body[((body[:, 1] - midline) * side > 0) & (body[:, 2] < ankle)]
        shell = shoes[ids]
        lower = shell[shell[:, 2] < ankle]
        if not len(foot) or not len(lower):
            raise ValueError("Missing foot or shoe below the ankle")
        def measurement(target, source):
            center = (source.max(axis=0) + source.min(axis=0))[:2] / 2
            shift = (target.max(axis=0) + target.min(axis=0))[:2] / 2 - center
            span = np.ptp(source[:, :2], axis=0)
            scale = np.clip((np.ptp(target[:, :2], axis=0) + margin) / np.maximum(span, 1e-9), 1, max_scale)
            return np.r_[center, shift, scale]
        ankle_fit = measurement(foot, lower)
        ankle_fit[-2:] = 1.0  # Preserve sole, toe and heel proportions.
        samples = [[ankle, *ankle_fit]]
        body_at = sided_sections(body, body_faces, side)
        shoe_at = sided_sections(shoes, shoe_faces, side)
        for z in levels[levels > ankle]:
            target, source = body_at(z), shoe_at(z)
            if len(target) >= 4 and len(source) >= 4:
                samples.append([z, *measurement(target, source)])
        if len(samples) < 2:
            raise ValueError("No matching shaft section on this leg")
        values = np.array(samples)
        center, shift, scale = np.split(np.stack([
            np.interp(shell[:, 2], values[:, 0], column) for column in values[:, 1:].T
        ], axis=1), 3, axis=1)
        return ids, shift + (shell[:, :2] - center) * (scale - 1)

    if parallel:
        with ThreadPoolExecutor(max_workers=2) as pool:
            updates = list(pool.map(fit_side, (-1, 1)))
    else:
        updates = map(fit_side, (-1, 1))
    for ids, delta in updates:
        result[ids, :2] += delta
    return result
