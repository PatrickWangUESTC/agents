"""Explicit material-region edits inside Blender; no automatic anatomy inference."""
import hashlib
import json
from pathlib import Path
import re

import bpy
import numpy as np


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fingerprint(obj):
    """Bind polygon masks to coordinates, topology and UV layout, not names."""
    mesh = obj.data
    h = hashlib.sha256()
    for items, field, width, dtype in [(mesh.vertices, 'co', 3, np.float32),
                                     (mesh.loops, 'vertex_index', 1, np.int32),
                                     (mesh.polygons, 'loop_total', 1, np.int32)]:
        a = np.empty(len(items) * width, dtype=dtype)
        items.foreach_get(field, a)
        if not np.isfinite(a).all():
            raise ValueError('Nonfinite geometry')
        h.update(str(a.shape).encode());h.update(a.tobytes())
    for uv in mesh.uv_layers:
        a = np.empty(len(uv.data) * 2, dtype=np.float32)
        uv.data.foreach_get('uv', a)
        if not np.isfinite(a).all():
            raise ValueError('Nonfinite UVs')
        h.update(uv.name.encode());h.update(a.tobytes())
    return h.hexdigest()


def principled(material):
    if material is None or not material.use_nodes:
        raise ValueError('Region needs a node material')
    nodes = [n for n in material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED']
    outputs = [n for n in material.node_tree.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output]
    if len(nodes) != 1 or len(outputs) != 1:
        raise ValueError('Expected one Principled shader and active output')
    links = outputs[0].inputs['Surface'].links
    if len(links) != 1 or links[0].from_node != nodes[0]:
        raise ValueError('Principled must directly feed Surface')
    return nodes[0]


def apply(config_path, out):
    config_path = Path(config_path).resolve();out = Path(out)
    config = json.loads(config_path.read_text())
    regions = config.get('regions')
    if not isinstance(regions, list) or not regions:
        raise ValueError('Need nonempty regions')
    records = [];used = {};objects = {};names = set()
    # Preflight all masks and shaders before mutating any scene data.
    for row in regions:
        name = row.get('name', '')
        if not re.fullmatch(r'[a-zA-Z0-9_-]+', name) or name in names:
            raise ValueError('Region names must be unique safe identifiers')
        names.add(name)
        obj = bpy.context.scene.objects.get(row.get('object', ''))
        if obj is None or obj.type != 'MESH' or obj.modifiers or obj.data.shape_keys:
            raise ValueError('Expected an explicit static mesh without modifiers/morphs')
        signature = fingerprint(obj)
        if signature != row.get('mesh_sha256'):
            raise ValueError('Mask targets a different mesh fingerprint')
        mask_path = (config_path.parent / row['faces']['path']).resolve()
        if digest(mask_path) != row['faces'].get('sha256'):
            raise ValueError('Face mask hash mismatch')
        faces = json.loads(mask_path.read_text())
        if (not isinstance(faces, list) or not faces
                or any(type(i) is not int or i < 0 or i >= len(obj.data.polygons) for i in faces)
                or len(set(faces)) != len(faces)):
            raise ValueError('Invalid polygon indices')
        assigned = used.setdefault(obj.name, set())
        if assigned.intersection(faces):
            raise ValueError('Region masks overlap')
        assigned.update(faces)
        rgb = row.get('color_srgb')
        if (not isinstance(rgb, list) or len(rgb) != 3
                or any(type(x) not in (int, float) or not np.isfinite(x) or not 0 <= x <= 1 for x in rgb)
                or not isinstance(row.get('color_evidence'), str) or not row['color_evidence'].strip()):
            raise ValueError('Need finite sRGB color and reference evidence')
        for idx in {obj.data.polygons[i].material_index for i in faces}:
            if idx >= len(obj.data.materials):
                raise ValueError('Missing source material')
            principled(obj.data.materials[idx])
        objects[obj.name] = obj
        records.append((row, obj, faces, mask_path, signature))
    evidence = out / 'material-inputs'
    if evidence.exists() or (out / 'material-edit-report.json').exists():
        raise ValueError('Material evidence exists; use a new revision')
    evidence.mkdir(parents=True)
    (evidence / 'config.json').write_bytes(config_path.read_bytes())
    originals = {};transforms = {}
    for name, obj in objects.items():
        originals[name] = [p.material_index for p in obj.data.polygons]
        transforms[name] = [list(r) for r in obj.matrix_world]
        obj.data = obj.data.copy()  # Never mutate a shared mesh owner.
    results = []
    for row, obj, faces, mask_path, signature in records:
        (evidence / (row['name'] + '-faces.json')).write_bytes(mask_path.read_bytes())
        rgb = np.array(row['color_srgb'], dtype=float)
        linear = np.where(rgb <= .04045, rgb / 12.92, ((rgb + .055) / 1.055) ** 2.4)
        slots = {}
        for face in faces:
            polygon = obj.data.polygons[face];old = polygon.material_index
            if old not in slots:
                material = obj.data.materials[old].copy()
                material.name = row['name'] + '__' + material.name
                shader = principled(material)
                for link in list(shader.inputs['Base Color'].links):
                    material.node_tree.links.remove(link)
                shader.inputs['Base Color'].default_value = (*linear, 1.)
                material.diffuse_color = (*linear, 1.)
                obj.data.materials.append(material);slots[old] = len(obj.data.materials) - 1
            polygon.material_index = slots[old]
        if fingerprint(obj) != signature or transforms[obj.name] != [list(r) for r in obj.matrix_world]:
            raise RuntimeError('Protected geometry/UV/transform changed')
        results.append({'name': row['name'], 'object': obj.name, 'faces': len(faces),
                        'mask_sha256': digest(mask_path), 'mesh_sha256': signature,
                        'color_srgb': rgb.tolist(), 'color_linear': linear.tolist(),
                        'color_evidence': row['color_evidence']})
    for name, obj in objects.items():
        if any(p.material_index != originals[name][i] for i, p in enumerate(obj.data.polygons) if i not in used[name]):
            raise RuntimeError('Non-target material assignment changed')
    report = {'status': 'pass', 'scope': 'Explicit material assignment only; mask semantics and visual quality not certified',
              'regions': results, 'geometry_uv_transform': 'unchanged',
              'non_target_assignments': 'unchanged', 'config_sha256': digest(config_path)}
    (out / 'material-edit-report.json').write_text(json.dumps(report, indent=2) + '\n')
    return report
