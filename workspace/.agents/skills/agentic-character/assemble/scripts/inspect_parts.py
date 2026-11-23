"""Inspect embedded static GLBs in one Blender process; cache neutral object-space views."""
import argparse
import hashlib
import json
import struct
import sys
import tempfile
from pathlib import Path
from time import perf_counter

import bpy
from mathutils import Vector


def fingerprint(path):
    raw = path.read_bytes()
    if raw[:4] != b'glTF' or raw[16:20] != b'JSON':
        raise ValueError(f'Expected a GLB: {path}')
    size, = struct.unpack_from('<I', raw, 12)
    doc = json.loads(raw[20:20+size])
    external = any(e.get('uri') and not e['uri'].startswith('data:')
                   for key in ('images','buffers') for e in doc.get(key, []))
    if external:
        raise ValueError(f'Pack external textures and buffers before caching: {path}')
    return hashlib.sha256(raw).hexdigest()


def inspect(path, folder):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(path))
    meshes = [o for o in bpy.context.selected_objects if o.type == 'MESH']
    if not meshes:
        raise ValueError(f'No mesh in {path}')
    pts = [o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    center, span = (lo+hi)/2, (hi-lo).length
    if span <= 0:
        raise ValueError(f'Empty extent: {path}')
    s = bpy.context.scene
    s.render.engine = 'BLENDER_WORKBENCH'
    s.display.shading.color_type = 'TEXTURE'
    s.display.shading.light = 'FLAT'
    s.view_settings.view_transform = 'Standard'
    s.render.resolution_x = s.render.resolution_y = 384
    s.render.resolution_percentage = 100
    bpy.ops.object.camera_add()
    cam = bpy.context.object
    s.camera = cam
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = span * 1.06
    cam.data.clip_start, cam.data.clip_end = span/1000, span*10
    for name, direction in AXES.items():
        axis = Vector(direction)
        cam.location = center + 3*span*axis
        cam.rotation_euler = (-axis).to_track_quat('-Z','Y').to_euler()
        s.render.filepath = str(folder/(name+'.png'))
        bpy.ops.render.render(write_still=True)
    return dict(min=list(lo),max=list(hi),vertices=len(pts),objects=[o.name for o in meshes])


AXES = {'plus-x':(1,0,0),'plus-y':(0,1,0),'minus-x':(-1,0,0),'minus-y':(0,-1,0)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cache', type=Path)
    parser.add_argument('inputs', type=Path, nargs='+')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    cache = args.cache.resolve()
    cache.mkdir(parents=True, exist_ok=True)
    version = hashlib.sha256(Path(__file__).read_bytes() + bpy.app.build_hash).hexdigest()
    started = perf_counter()
    parts = []
    for path in args.inputs:
        sha = fingerprint(path)
        folder = cache/version/sha
        record = folder/'bounds.json'
        reused = record.exists() and all((folder/(n+'.png')).is_file() for n in AXES)
        if not reused:
            folder.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=folder.parent) as tmp:
                work = Path(tmp)/'entry'
                work.mkdir()
                (work/'bounds.json').write_text(json.dumps(inspect(path.resolve(),work)))
                folder.mkdir(exist_ok=True)
                for name in [*(k+'.png' for k in AXES), 'bounds.json']:
                    (work/name).replace(folder/name)
        parts.append(dict(input=str(path.resolve()),sha256=sha,views=str(folder),
                          bounds=json.loads(record.read_text()),reused=reused))
    print('ASSEMBLE_INTAKE '+json.dumps(dict(seconds=perf_counter()-started,parts=parts)))


if __name__ == '__main__':
    main()
