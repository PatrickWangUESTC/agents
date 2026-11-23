"""Capture matched local views and geometry evidence from saved static revisions."""
import argparse
import json
import sys
from pathlib import Path
from time import perf_counter

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def load(path, args):
    bpy.ops.wm.open_mainfile(filepath=str(path.resolve()))
    scene = bpy.context.scene
    meshes = {o.name: o for o in scene.objects if o.type == 'MESH'}
    required = {args.part, *args.neighbor, *args.occluder}
    missing = required - meshes.keys()
    if missing:
        raise ValueError(f'Missing mesh objects: {sorted(missing)}')
    for obj in meshes.values():
        if obj.hide_render or not obj.visible_get() or any(m.type == 'MASK' for m in obj.modifiers):
            raise ValueError(f'Expected visible unmasked static mesh: {obj.name}')
    return scene, meshes


def bounds(obj):
    corners = [obj.matrix_world @ Vector(p) for p in obj.bound_box]
    lo = Vector([min(p[i] for p in corners) for i in range(3)])
    hi = Vector([max(p[i] for p in corners) for i in range(3)])
    return (lo + hi) / 2, (hi - lo).length * 1.12


def capture(path, label, args, axis, frame, loaded=None):
    started = perf_counter()
    scene, meshes = loaded or load(path, args)
    obj = meshes[args.part]
    if frame is None:
        frame = bounds(obj)
    center, scale = frame
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.display.shading.light = 'FLAT'
    scene.display.shading.color_type = 'TEXTURE'
    scene.view_settings.view_transform = 'Standard'
    scene.render.resolution_x = scene.render.resolution_y = 512
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    scene.camera = camera
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = scale
    camera.data.clip_start = scale / 1000
    camera.data.clip_end = scale * 10
    camera.location = center + 3 * scale * axis
    camera.rotation_euler = (-axis).to_track_quat('-Z', 'Y').to_euler()

    def render(tag, hidden):
        for name, mesh in meshes.items():
            mesh.hide_render = name in hidden
        scene.render.filepath = str(args.output.resolve() / f'{label}-{tag}.png')
        bpy.ops.render.render(write_still=True)

    graph = bpy.context.evaluated_depsgraph_get()
    def world_tree(mesh):
        evaluated = mesh.evaluated_get(graph)
        data = evaluated.data
        data.calc_loop_triangles()
        return BVHTree.FromPolygons([evaluated.matrix_world @ v.co for v in data.vertices],
                                   [tuple(t.vertices) for t in data.loop_triangles],
                                   all_triangles=True)
    target = world_tree(obj)
    pairs = {name: len(target.overlap(world_tree(meshes[name])))
             for name in dict.fromkeys(args.neighbor + args.occluder)}
    render('all', set())
    if args.occluder:
        render('without-occluders', set(args.occluder))
    render('part', meshes.keys() - {args.part})
    return frame, dict(scene=str(path), seconds=perf_counter()-started, target_neighbor_pairs=pairs)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('candidate', type=Path)
    cli.add_argument('output', type=Path)
    cli.add_argument('--before', type=Path)
    cli.add_argument('--part', required=True)
    cli.add_argument('--neighbor', action='append', default=[])
    cli.add_argument('--occluder', action='append', default=[])
    cli.add_argument('--front', type=float, nargs=2, required=True, metavar=('X','Y'))
    cli.add_argument('--view', choices=['front','left','back','right'], required=True)
    a = cli.parse_args(sys.argv[sys.argv.index('--')+1:])
    front = Vector((*a.front, 0))
    if not front.length or a.part in a.neighbor + a.occluder:
        cli.error('Supply a horizontal camera direction and distinct target and neighbors')
    front.normalize()
    left = Vector((-front.y, front.x, 0))
    axis = dict(front=front,left=left,back=-front,right=-left)[a.view]
    a.output.mkdir(parents=True, exist_ok=False)
    report = dict(part=a.part, view=a.view, occluders=a.occluder)
    frame = None
    if a.before:
        # Include large silhouette corrections in the same frame for both rows.
        _, meshes = load(a.candidate, a)
        new_center, new_scale = bounds(meshes[a.part])
        loaded = load(a.before, a)
        old_center, old_scale = bounds(loaded[1][a.part])
        frame = ((new_center + old_center) / 2,
                 max(new_scale, old_scale) + (new_center-old_center).length)
        frame, report['before'] = capture(a.before,'before',a,axis,frame,loaded)
    frame, report['candidate'] = capture(a.candidate,'candidate',a,axis,frame)
    report.update(center=list(frame[0]), scale=frame[1])
    (a.output/'diagnosis.json').write_text(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
