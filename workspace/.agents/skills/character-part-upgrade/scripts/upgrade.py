"""Blender: replace explicitly separated static parts on a new checkpoint."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import bpy
from mathutils import Matrix


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def signature(obj):
    mesh = obj.data
    payload = {'vertices': [list(v.co) for v in mesh.vertices],
               'faces': [list(p.vertices) for p in mesh.polygons],
               'material_indices': [p.material_index for p in mesh.polygons],
               'uv': {u.name: [list(v.uv) for v in u.data] for u in mesh.uv_layers},
               'matrix': [list(row) for row in obj.matrix_world],
               'materials': [m.name if m else None for m in mesh.materials]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def execute(config, out):
    for key in ('source', 'candidate'):
        assert sha(config[key]['path']) == config[key]['sha256'], f'{key} changed'
    bpy.ops.wm.open_mainfile(filepath=str(Path(config['source']['path']).resolve()))
    original = {o.name: o for o in bpy.context.scene.objects if o.type == 'MESH'}
    targets = config['targets']
    if not targets or len(set(targets)) != len(targets) or not set(targets) <= set(original):
        raise ValueError('Target must be explicit separated mesh objects; fused regions require a reviewed split first')
    if any(o.modifiers or o.data.shape_keys or o.vertex_groups for o in original.values()):
        raise ValueError('This replacement helper accepts static assets only; rigged/morph assets need a transfer workflow')
    if any(original[n].children or original[n].parent for n in targets):
        raise ValueError('Resolve target parent/children explicitly before replacement')
    before = {n: signature(o) for n, o in original.items() if n not in targets}
    candidate = Path(config['candidate']['path']).resolve()
    before_objects = set(bpy.data.objects)
    if candidate.suffix == '.blend':
        with bpy.data.libraries.load(str(candidate), link=False) as (src, dst):
            requested = config['candidate']['objects']
            if not set(requested) <= set(src.objects):
                raise ValueError('Candidate object missing')
            dst.objects = list(requested)
        imported = list(dst.objects)
        for obj in imported:
            bpy.context.scene.collection.objects.link(obj)
    elif candidate.suffix == '.glb':
        bpy.ops.import_scene.gltf(filepath=str(candidate))
        imported = list(set(bpy.data.objects) - before_objects)
    else:
        raise ValueError('Candidate must be a .blend or .glb; convert in an inspected revision first')
    if not imported or any(o.type != 'MESH' or o.parent or o.modifiers or o.data.shape_keys for o in imported):
        raise ValueError('Use a standalone static mesh candidate without parent, rig or morph dependencies')
    placements = config['placements']
    if set(placements) != {o.name for o in imported}:
        raise ValueError(f'Explicit placement needed for every imported object: {[o.name for o in imported]}')
    for obj in imported:
        matrix = Matrix(placements[obj.name])
        if len(matrix) != 4 or any(not __import__('math').isfinite(x) for row in matrix for x in row) or abs(matrix.determinant()) < 1e-12:
            raise ValueError('Invalid placement matrix')
        obj.matrix_world = matrix
    for name in targets:
        bpy.data.objects.remove(original[name], do_unlink=True)
    after = {n: signature(bpy.data.objects[n]) for n in before}
    assert before == after, 'Protected mesh state changed'
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(out / 'candidate.blend'))
    report = {'status': 'produced', 'source': config['source'], 'candidate': config['candidate'],
              'removed': targets, 'added': [o.name for o in imported],
              'protected_before': before, 'protected_after': after,
              'checks': {'unaffected_mesh_state': 'pass', 'neck_seam': 'not_run',
                         'intersections': 'not_run', 'visual_review': 'not_run'},
              'output_sha256': sha(out / 'candidate.blend'),
              'scope': 'Separated static object replacement; no semantic segmentation, seam welding, rig or visual acceptance'}
    (out / 'upgrade-report.json').write_text(json.dumps(report, indent=2) + '\n')


def main():
    config_path, destination = sys.argv[sys.argv.index('--') + 1:]
    out = Path(destination).resolve()
    out.mkdir(parents=True, exist_ok=False)
    config = json.loads(Path(config_path).read_text())
    (out / 'config.json').write_text(json.dumps(config, indent=2))
    shutil.copy2(__file__, out / 'upgrade.py')
    execute(config, out)


if __name__ == '__main__':
    main()
