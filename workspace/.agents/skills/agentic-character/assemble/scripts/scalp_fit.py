"""Blender -b BASE.blend -P scalp_fit.py -- CONFIG.json RESULT.json.

Fit an intact hair mesh by positive uniform scale and translation in world space.
Configuration specifies head, body, hair, cap_materials and reference_height_ratio
(hair height / complete figure height). The +Z axis is up, the face points -Y.
"""
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def surface(obj, materials=None):
    vertices = np.asarray([obj.matrix_world @ v.co for v in obj.data.vertices])
    obj.data.calc_loop_triangles()
    tris = [tuple(t.vertices) for t in obj.data.loop_triangles
            if materials is None or obj.material_slots[t.material_index].name in materials]
    if not tris:
        raise ValueError(f"Empty surface selection for {obj.name}")
    used = vertices[np.unique(tris)]
    return used, BVHTree.FromPolygons(vertices.tolist(), tris, all_triangles=True)


def measure_rays(head, head_tree):
    lo, hi = head.min(0), head.max(0)
    width = hi[0] - lo[0]
    origin = (lo + hi) / 2
    origin[2] += .12 * (hi[2] - lo[2])
    samples = []
    for elevation in (5, 20, 35, 50, 65, 80, 90):
        elevation_rad = math.radians(elevation)
        for azimuth in range(0, 360, 360 if elevation == 90 else 10):
            a = math.radians(azimuth)
            direction = np.array([math.sin(a)*math.cos(elevation_rad),
                                  -math.cos(a)*math.cos(elevation_rad), math.sin(elevation_rad)])
            # Exclude eyes, cheeks and the open forehead below the fringe.
            if direction[1] < -.3 and elevation < 65:
                continue
            hit = head_tree.ray_cast(Vector(origin + direction*width*2), Vector(-direction), width*2)[0]
            if hit is not None:
                samples.append((direction, np.dot(np.array(hit)-origin, direction)))
    return origin, width, samples


def fit_scalp(config):
    objs = {role: bpy.data.objects[config[role]] for role in ('hair','head','body')}
    head, tree = surface(objs['head'])
    body, _ = surface(objs['body'])
    hair, _ = surface(objs['hair'])
    cap, cap_tree = surface(objs['hair'], config['cap_materials'])
    origin, width, samples = measure_rays(head, tree)
    if not samples:
        raise ValueError('No scalp rays hit the fixed head')
    target = config['reference_height_ratio'] * (head[:,2].max()-body[:,2].min())
    cap_center = (cap.max(0)+cap.min(0))*.5
    def metrics(k, shift):
        gaps = []
        for direction, radius in samples:
            start = (origin+direction*width*2-shift)/k
            hit = cap_tree.ray_cast(Vector(start), Vector(-direction), 2*width/k)[0]
            if hit is None:
                gaps.append(-width)
            else:
                gaps.append(np.dot(k*np.array(hit)+shift-origin, direction)-radius)
        gaps = np.asarray(gaps)/width
        hair_height = k*np.ptp(hair[:,2])
        loss = (np.mean(np.maximum(.008-gaps,0))*7
                + np.mean(np.abs(gaps-.035)) + .8*abs(math.log(hair_height/target)))
        return float(loss), dict(rays=len(gaps), exposed=int(sum(gaps<0)),
                                 coverage=float(np.mean(gaps>=0)), median_clearance_head_widths=float(np.median(gaps)),
                                 p95_clearance_head_widths=float(np.quantile(gaps,.95)), hair_height=float(hair_height))
    initial = metrics(1., np.zeros(3))[1]
    k = target/np.ptp(hair[:,2])
    center = origin.copy()
    center[2] = head[:,2].max()+.035*width-k*(cap[:,2].max()-cap_center[2])
    def evaluate(x):
        factor=k*math.exp(x[0])
        translation=center+x[1:]*width-factor*cap_center
        return metrics(factor,translation)[0],factor,translation
    x=np.zeros(4)
    for step in (.08,.04,.02,.01,.005,.002):
        for _ in range(20):
            candidates=[x]+[x+direction*step for direction in np.vstack([np.eye(4),-np.eye(4)])]
            selected=min(candidates,key=lambda v:evaluate(v)[0])
            if np.array_equal(selected,x):
                break
            x=selected
    _,k,shift=evaluate(x)
    fitted=metrics(k,shift)[1]
    return dict(before=initial, after=fitted, world_scale=k,
                world_translation=shift.tolist(), target_height=target)


if __name__=='__main__':
    config_path, report_path = map(Path, sys.argv[sys.argv.index('--')+1:])
    report_path.write_text(json.dumps(fit_scalp(json.loads(config_path.read_text())), indent=2))
