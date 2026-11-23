"""Check corresponding source-surface regions before spending time on review images."""
import json

import numpy as np


def edges(triangles):
    pairs = triangles[:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2)
    return np.unique(np.sort(pairs, axis=1), axis=0)


def check_regions(specs, plan_dir, destination, geometry):
    results = {}
    try:
        if not isinstance(specs, dict) or not specs:
            raise ValueError("geometry_limits needs at least one named region")
        for name, spec in specs.items():
            result = results[name] = {}
            points, faces = geometry(spec["part"])
            with np.load(plan_dir / spec["reference"], allow_pickle=False) as data:
                base, triangles = data["p"], data["t"]
                ids = data["ids"] if "ids" in data else np.arange(len(base))
            if (base.ndim != 2 or base.shape[1] != 3 or triangles.ndim != 2
                    or triangles.shape[1] != 3 or triangles.dtype.kind not in "iu"
                    or not triangles.size or triangles.min() < 0 or triangles.max() >= len(base)
                    or ids.ndim != 1 or ids.dtype.kind not in "iu" or not len(ids)
                    or ids.min() < 0 or ids.max() >= min(len(base), len(points))):
                raise ValueError(f"{name}: invalid reference or vertex correspondence")
            region = np.zeros(max(len(points), len(base)), dtype=bool)
            region[ids] = True
            def selected_edges(ts):
                subset = ts[region[ts].sum(axis=1) >= 2]
                e = edges(subset)
                return e[region[e].all(axis=1)]
            e = selected_edges(triangles)
            current = selected_edges(faces)
            if not set(map(tuple, e)).issubset(map(tuple, current)):
                raise ValueError(f"{name}: source edges missing in candidate")
            def lengths(p):
                return np.linalg.norm(p[e[:, 0]] - p[e[:, 1]], axis=1)
            original = lengths(base)
            valid = original > 0
            if not valid.any() or not np.isfinite(base[ids]).all() or not np.isfinite(points[ids]).all():
                raise ValueError(f"{name}: empty or nonfinite region")
            ratios = lengths(points)[valid] / original[valid]
            measured = {
                "max_displacement": float(np.linalg.norm(points[ids] - base[ids], axis=1).max()),
                "max_edge_ratio": float(ratios.max()),
                "min_edge_ratio": float(ratios.min()),
                "max_p95_edge_ratio": float(np.percentile(ratios, 95)),
            }
            limits = {k: v for k, v in spec.items() if k not in ("part", "reference")}
            if not limits or not limits.keys() <= measured.keys():
                raise ValueError(f"{name}: missing or unknown limit")
            for k, v in limits.items():
                if not isinstance(v, (int, float)) or not np.isfinite(v) or v < 0:
                    raise ValueError(f"{name}: invalid {k}")
            result.update(measured=measured, limits=limits, failed=[
                k for k, v in limits.items()
                if (measured[k] < v if k == "min_edge_ratio" else measured[k] > v)
            ])
        passed = all(not r["failed"] for r in results.values())
        report = {"passed": passed, "regions": results}
    except (KeyError, TypeError, IndexError, ValueError, OSError) as exc:
        report = {"passed": False, "regions": results, "error": str(exc)}
    (destination / "preflight.json").write_text(json.dumps(report, indent=2))
    if not report["passed"]:
        raise ValueError(f"Geometry preflight failed; see {destination / 'preflight.json'}")
