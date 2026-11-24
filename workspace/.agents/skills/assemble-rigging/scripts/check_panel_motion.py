"""Audit one pre-registered garment region at one time on a fixed topology."""

import numpy as np


def check_panel_motion(vertices, stages, *, body_height, limit_ratio):
    """Supply ordered (name, world XYZ) stages starting with accepted skinning.

    The caller records frame and region, and requires a pass at every sample.
    limit_ratio is the predeclared displacement budget divided by body_height.
    """
    ids = np.asarray(vertices)
    if ids.ndim != 1 or not ids.size or ids.dtype.kind not in "iu" or ids.min() < 0:
        raise ValueError("Expected nonempty vertex indices from the rest mesh")
    if not np.isfinite(body_height) or body_height <= 0:
        raise ValueError("Expected positive finite rest body height")
    if not np.isfinite(limit_ratio) or limit_ratio < 0:
        raise ValueError("Expected a finite nonnegative region budget")
    baseline = None
    layers = {}
    names = set()
    for name, xyz in stages:
        xyz = np.asarray(xyz)
        if not name or name in names:
            raise ValueError("Expected unique stage names in evaluation order")
        names.add(name)
        if xyz.ndim != 2 or xyz.shape[1] != 3 or ids.max() >= len(xyz):
            raise ValueError("Stage does not cover the registered vertex indices")
        points = xyz[ids].astype(float)
        if not np.isfinite(points).all():
            raise ValueError("Nonfinite garment coordinates")
        if baseline is None:
            baseline = points
            shape = xyz.shape
            continue
        if xyz.shape != shape:
            raise ValueError("Stage topology differs from baseline")
        ratios = np.linalg.norm(points - baseline, axis=1) / body_height
        worst = int(ratios.argmax())
        layers[name] = dict(vertex=int(ids[worst]), maximum=float(ratios[worst]),
                            p95=float(np.percentile(ratios, 95)))
    if not layers:
        raise ValueError("Missing baseline or evaluated stages")
    return dict(passed=all(v["maximum"] <= limit_ratio for v in layers.values()),
                checked=len(ids), limit_ratio=limit_ratio, layers=layers)
