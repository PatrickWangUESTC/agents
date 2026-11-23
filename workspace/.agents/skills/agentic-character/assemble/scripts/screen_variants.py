"""Screen saved local repairs in one Blender process using paired visibility renders."""
import argparse
from html import escape
import json
from pathlib import Path
import sys
from time import monotonic

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mathutils import Vector

from clearance import surface, tree
from review_views import render_review


def read_rgb(path):
    image = bpy.data.images.load(str(path), check_existing=False)
    try:
        image.colorspace_settings.name = 'Non-Color'
        width, height = image.size
        pixels = np.empty(width * height * 4, dtype=np.float32)
        image.pixels.foreach_get(pixels)
        return np.rint(255 * pixels.reshape(height, width, 4)[::-1, :, :3]).astype(np.int16)
    finally:
        bpy.data.images.remove(image)


def measure(folder, view, probe):
    full = read_rgb(folder / f'outer-{view}.png')
    isolated = read_rgb(folder / f'isolated-{view}.png')
    h, w = full.shape[:2]
    x, y, right, bottom = probe.get('roi', [0, 0, w, h])
    if not (0 <= x < right <= w and 0 <= y < bottom <= h):
        raise ValueError('roi must be a nonempty rectangle inside the rendered image')
    delta = np.abs(full[y:bottom, x:right] - isolated[y:bottom, x:right]).max(axis=2)
    rows, cols = np.nonzero(delta > probe['rgb_tolerance'])
    box = None
    if len(rows):
        box = [int(cols.min()+x), int(rows.min()+y), int(cols.max()+x+1), int(rows.max()+y+1)]
    finding = dict(pixels=len(rows), bbox=box, image_size=[w, h])
    if len(rows) > probe['max_pixels'] and 'outer' in probe:
        picks = np.linspace(0, len(rows)-1, min(64, len(rows)), dtype=int)
        finding['surface_samples'] = locate(probe, cols[picks]+x, rows[picks]+y, w, h)
    return finding


def locate(probe, cols, rows, width, height):
    """Trace failing pixels into the original scene for the next bounded repair."""
    scene = bpy.context.scene
    if scene.render.use_border and scene.render.use_crop_to_border:
        raise ValueError("World localization requires an uncropped camera frame; use a pixel roi")
    camera = scene.camera
    frame = np.array([tuple(v) for v in camera.data.view_frame(scene=scene)])
    lo, hi = frame.min(0), frame.max(0)
    direction = camera.matrix_world.to_quaternion() @ Vector((0, 0, -1))
    inner, outer = [tree(*surface(scene.objects[probe[k]])) for k in ('inner', 'outer')]
    samples = []
    for col, row in zip(cols, rows):
        x = lo[0] + (col+.5)/width * (hi[0]-lo[0])
        y = hi[1] - (row+.5)/height * (hi[1]-lo[1])
        origin = camera.matrix_world @ Vector((x, y, 0))
        pos, _, face, dist = inner.ray_cast(origin, direction)
        if pos is None:
            continue
        outer_hit, _, outer_face, outer_dist = outer.ray_cast(origin, direction)
        if outer_face is not None and outer_dist < dist:
            continue
        near, _, nearest_face, gap = outer.find_nearest(pos)
        samples.append(dict(pixel=[int(col), int(row)], inner_face=face,
                            inner_world=list(pos), ray_outer_face=outer_face,
                            ray_outer_world=list(outer_hit) if outer_hit is not None else None,
                            nearest_outer_face=nearest_face,
                            nearest_outer_world=list(near), nearest_distance=gap,
                            depth_to_outer=None if outer_face is None else outer_dist-dist))
    return samples


def write_overview(folder, rows):
    page = ['<!doctype html><meta charset="utf-8"><title>Local repair review</title>',
            '<style>body{font:16px system-ui;margin:2rem}figure{display:inline-block;'
            'margin:0 .5rem .5rem 0}a{position:relative;display:inline-block}img{width:18rem;'
            'max-width:42vw;display:block}i{box-sizing:border-box;border:2px solid #ff4681;'
            'position:absolute;pointer-events:none}</style>']
    for i, row in enumerate(rows):
        page.append(f"<h2>{escape(Path(row['scene']).name)} · {escape(row['status'])}</h2>")
        if row['status'] == 'shape_limit_failed':
            page.append(f'<a href="{i:03d}/00/preflight.json">Shape measurements</a>')
        for j, probe in enumerate(row['probes']):
            page.append(f"<p>{escape(probe['frame'])} / {escape(probe['view'])}"
                        f" · {probe['pixels']} changed pixels</p>")
            box = probe['bbox']
            overlay = ''
            if box:
                x, y, right, bottom = box
                w, h = probe['image_size']
                overlay = (f'<i style="left:{100*x/w}%;top:{100*y/h}%;'
                           f'width:{100*(right-x)/w}%;height:{100*(bottom-y)/h}%"></i>')
            for label, caption in [('outer', 'Dressed'), ('isolated', 'Inner layer hidden')]:
                path = f"{i:03d}/{j:02d}/{label}-{probe['view']}.png"
                page.append(f'<figure><a href="{path}"><img src="{path}" alt="{caption}">'
                            f'{overlay}</a><figcaption>{caption}</figcaption></figure>')
    (folder / 'overview.html').write_text(''.join(page), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('scenes', nargs='+', type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    plan = json.loads(args.plan.read_text())
    probes = plan['screen']
    if not probes:
        raise ValueError('Expected at least one screen probe')
    for probe in probes:
        frame = plan['frames'][probe['frame']]
        if probe.get('outer') == probe['inner'] or probe.get('outer') in frame.get('hide', []):
            raise ValueError('Expected a distinct visible outer mesh')
        if probe['inner'] in frame.get('hide', []):
            raise ValueError('Inner surface already hidden in base frame')
        for key, upper in [('rgb_tolerance', 255), ('max_pixels', float('inf'))]:
            if type(probe[key]) is not int or not 0 <= probe[key] <= upper:
                raise ValueError(f'Invalid {key}')
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    results = []
    for i, scene in enumerate(args.scenes):
        start = monotonic()
        bpy.ops.wm.open_mainfile(filepath=str(scene.resolve()))
        folder = args.output / f'{i:03d}'
        row = dict(scene=str(scene.resolve()), status='needs_visual_review', probes=[])
        for j, probe in enumerate(probes):
            frame = plan['frames'][probe['frame']]
            isolated = dict(frame, hide=[*frame.get('hide', []), probe['inner']])
            subplan = dict(plan, frames=dict(outer=frame, isolated=isolated))
            if j:
                subplan.pop('geometry_limits', None)
            view = probe['view']
            dest = folder / f'{j:02d}'
            try:
                render_review(subplan, args.plan.resolve().parent, dest,
                              [f'outer={view}', f'isolated={view}'])
            except ValueError:
                preflight = dest / 'preflight.json'
                if not preflight.exists():
                    raise
                report = json.loads(preflight.read_text())
                if report.get('error') or report['passed']:
                    raise
                row['status'] = 'shape_limit_failed'
                break
            finding = measure(dest, view, probe)
            row['probes'].append(dict(**finding, frame=probe['frame'], view=view))
            if finding['pixels'] > probe['max_pixels']:
                row['status'] = 'visibility_limit_failed'
                break
        row['seconds'] = monotonic() - start
        results.append(row)
        (args.output / 'screen.json').write_text(json.dumps(results, indent=2))
        write_overview(args.output, results)


if __name__ == '__main__':
    main()
