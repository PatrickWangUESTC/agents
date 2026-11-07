"""Blender-only static character -> explicit FK rig, validation clips and exports.

blender -b --python-exit-code 1 --python rig_blender.py -- CONFIG NEW_OUTPUT
Case policy and joints must be reviewed for the actual input; not a universal autorigger.
"""
import hashlib
import heapq
import json
import math
from pathlib import Path
import shutil
import sys

import bpy
import numpy as np
from mathutils import Quaternion, Vector
from mathutils.kdtree import KDTree

ALIASES = {}


def named(name):
    return ALIASES.get(name, name)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def coords(obj, evaluated=False):
    target = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()) if evaluated else obj
    mesh = target.to_mesh() if evaluated else target.data
    a = np.empty(len(mesh.vertices) * 3, np.float32)
    mesh.vertices.foreach_get('co', a)
    matrix = np.asarray(target.matrix_world)
    world = np.einsum('ij,nj->ni', matrix[:3, :3], a.reshape(-1, 3)) + matrix[:3, 3]
    if evaluated:
        target.to_mesh_clear()
    return world


def signature(obj):
    mesh = obj.data
    result = {}
    for name, seq, prop, size, dtype in [('co', mesh.vertices, 'co', 3, np.float32),
                                      ('indices', mesh.loops, 'vertex_index', 1, np.int32)]:
        a = np.empty(len(seq) * size, dtype)
        seq.foreach_get(prop, a)
        result[name] = hashlib.sha256(a.tobytes()).hexdigest()
    result['uv'] = {}
    for layer in mesh.uv_layers:
        a = np.empty(len(mesh.loops) * 2, np.float32)
        layer.data.foreach_get('uv', a)
        result['uv'][layer.name] = hashlib.sha256(a.tobytes()).hexdigest()
    mesh.calc_loop_triangles()
    result.update(vertices=len(mesh.vertices), triangles=len(mesh.loop_triangles),
                  materials=[m.name for m in mesh.materials if m])
    return result


def base_colors(obj):
    mesh = obj.data
    if len(mesh.materials) != 1 or not mesh.uv_layers.active:
        raise ValueError('Case policy needs one base-color texture and UV layer')
    shader = next(n for n in mesh.materials[0].node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    image = shader.inputs['Base Color'].links[0].from_node.image
    pixels = np.empty(len(image.pixels), np.float32)
    image.pixels.foreach_get(pixels)
    pixels = pixels.reshape(image.size[1], image.size[0], 4)
    uv = np.empty(len(mesh.loops) * 2, np.float32)
    mesh.uv_layers.active.data.foreach_get('uv', uv)
    uv = uv.reshape(-1, 2)
    ix = np.clip((uv[:, 0] * image.size[0]).astype(int), 0, image.size[0] - 1)
    iy = np.clip((uv[:, 1] * image.size[1]).astype(int), 0, image.size[1] - 1)
    vertex = np.empty(len(mesh.loops), np.int32)
    mesh.loops.foreach_get('vertex_index', vertex)
    colors = np.zeros((len(mesh.vertices), 3))
    for channel in range(3):
        colors[:, channel] = np.bincount(vertex, weights=pixels[iy, ix, channel], minlength=len(colors))
    colors /= np.maximum(np.bincount(vertex, minlength=len(colors)), 1)[:, None]
    return colors


def distance(points, a, b):
    d = b - a
    t = np.clip(np.einsum('ij,j->i', points - a, d) / np.dot(d, d), 0, 1)
    return np.linalg.norm(points - a - t[:, None] * d, axis=1)


def skeleton_weights(points, bones):
    real_index = {b['name']: i for i, b in enumerate(bones)}
    index = dict(real_index)
    index.update({old: real_index[new] for old, new in ALIASES.items()})
    w = np.zeros((len(points), len(bones)), np.float32)
    z, x = points[:, 2], points[:, 0]
    for i, b in enumerate(bones):
        if not b.get('deform', True) or b['name'].startswith(('hair_', 'skirt_')):
            continue
        w[:, i] = 1 / (distance(points, np.array(b['head']), np.array(b['tail'])) + .025) ** 4
    arm_union = np.zeros(len(points))
    leg_gate = np.clip((.22 - z) / .14, 0, 1)
    for side, sign in [('l', 1), ('r', -1)]:
        gate = np.clip((sign * x - (.15 + .28 * np.maximum(.5 - z, 0))) / .045 + .5, 0, 1)
        gate *= np.clip((z + .08) / .15, 0, 1)
        arm_union = np.maximum(arm_union, gate)
        for key in ['clavicle', 'upperarm', 'lowerarm', 'hand']:
            if key + '_' + side in index:
                w[:, index[key + '_' + side]] *= gate
        hand = bones[index['hand_' + side]]
        direction = np.array(hand['tail']) - np.array(hand['head'])
        direction /= np.linalg.norm(direction)
        progress = np.einsum('ij,j->i', points - np.array(hand['head']), direction)
        finger_gate = gate * np.clip((progress + .01) / .035, 0, 1)
        for name, idx in real_index.items():
            if ('Finger' in name or 'Thumb' in name) and name.endswith('_' + side.upper()):
                w[:, idx] *= finger_gate
        for key in ['thigh', 'calf', 'foot', 'ball']:
            w[:, index[key + '_' + side]] *= leg_gate * np.clip(sign * x / .025 + .5, 0, 1)
    for name in ['pelvis', 'spine_01', 'spine_02', 'upper_chest', 'neck_01', 'head']:
        if name in index:
            w[:, index[name]] *= (1 - .999 * arm_union)
    for name in ['spine_01', 'spine_02', 'upper_chest', 'neck_01', 'head']:
        if name in index:
            w[:, index[name]] *= np.clip((z + .05) / .15, 0, 1)
    head = z >= .67
    w[head] = 0
    w[head, index['head']] = 1
    w /= np.maximum(w.sum(axis=1, keepdims=True), 1e-12)
    assert np.all(w.sum(axis=1) > .99)
    return w


def hair_contact_weights(obj, points, hair, body_w, index, transition=.08, torso_tether=False):
    """Geodesic blend at fused hair/body contacts; mesh and UV seams untouched."""
    _, first, inverse = np.unique(np.round(points * 1e6).astype(np.int64), axis=0,
                                  return_index=True, return_inverse=True)
    count = np.bincount(inverse)
    labels = np.bincount(inverse, weights=hair.astype(float)) / count >= .5
    edges = np.empty(len(obj.data.edges) * 2, np.int32)
    obj.data.edges.foreach_get('vertices', edges)
    edges = np.sort(inverse[edges.reshape(-1, 2)], axis=1)
    edges = np.unique(edges[edges[:, 0] != edges[:, 1]], axis=0)
    src = np.concatenate([edges[:, 0], edges[:, 1]])
    dst = np.concatenate([edges[:, 1], edges[:, 0]])
    degree = np.bincount(src, minlength=len(first))
    # Remove isolated texture-label islands before identifying actual contacts.
    for _ in range(3):
        votes = np.bincount(src, weights=labels[dst], minlength=len(first)) / np.maximum(degree, 1)
        labels = np.where(votes > .7, True, np.where(votes < .3, False, labels))
    boundary = np.unique(src[labels[src] & ~labels[dst]])
    order = np.argsort(src)
    src, dst = src[order], dst[order]
    offsets = np.r_[0, np.cumsum(np.bincount(src, minlength=len(first)))]
    verts = points[first]
    costs = np.linalg.norm(verts[src] - verts[dst], axis=1)
    distances = np.full(len(first), np.inf)
    distances[boundary] = 0
    queue = [(0., int(i)) for i in boundary]
    heapq.heapify(queue)
    while queue:
        dist, i = heapq.heappop(queue)
        if dist != distances[i] or dist >= transition:
            continue
        for k in range(offsets[i], offsets[i+1]):
            j = int(dst[k]); value = dist + float(costs[k])
            if labels[j] and value < distances[j] and value < transition:
                distances[j] = value
                heapq.heappush(queue, (value, j))
    hair = labels[inverse]
    mix = np.clip(distances[inverse] / transition, 0, 1)
    result = body_w.copy()
    if torso_tether:
        # COM0 has no hair chain. Keep long hair on the head/torso hierarchy,
        # preventing nearby arm/finger weights from pulling fused hair surfaces.
        core_indices=[index[k] for k in ['pelvis','spine_01','spine_02','upper_chest','neck_01','head'] if k in index]
        core=body_w[hair][:,core_indices].copy()
        core/=np.maximum(core.sum(axis=1,keepdims=True),1e-12)
        result[hair]=0
        result[np.ix_(hair,core_indices)]=core*(1-mix[hair,None])
        head_mix=np.clip((points[hair,2]-.32)/.34,0,1)
        result[hair,index['head']]+=mix[hair]*head_mix
        result[hair,index.get('upper_chest',index['spine_02'])]+=mix[hair]*(1-head_mix)
    else:
        result[hair] *= (1 - mix[hair, None])
        result[hair, index['head']] += mix[hair]
    return result, hair, {'hair_vertices': int(hair.sum()), 'contact_vertices': int(len(boundary)),
                         'transition_distance_source_units': transition}


def share_seams(points, w):
    # Average coincident UV-split vertices without welding or altering geometry.
    _, inverse = np.unique(np.round(points * 1e6).astype(np.int64), axis=0, return_inverse=True)
    counts = np.bincount(inverse)
    for i in range(w.shape[1]):
        w[:, i] = (np.bincount(inverse, weights=w[:, i]) / counts)[inverse]
    return w


def assign(obj, w, bones):
    selected = np.argpartition(w, -4, axis=1)[:, -4:]
    top = np.take_along_axis(w, selected, axis=1)
    top /= np.maximum(top.sum(axis=1, keepdims=True), 1e-12)
    codes = np.rint(top * 4096).astype(np.int32)
    codes[np.arange(len(codes)), top.argmax(axis=1)] += 4096 - codes.sum(axis=1)
    groups = [obj.vertex_groups.new(name=b['name']) for b in bones]
    vertices = np.repeat(np.arange(len(w)), 4)
    keys = selected.ravel() * 4097 + codes.ravel()
    positive = codes.ravel() > 0
    vertices, keys = vertices[positive], keys[positive]
    order = np.argsort(keys)
    vertices, keys = vertices[order], keys[order]
    starts = np.r_[0, np.flatnonzero(np.diff(keys)) + 1, len(keys)]
    for a, b in zip(starts[:-1], starts[1:]):
        bone, code = divmod(int(keys[a]), 4097)
        groups[bone].add(vertices[a:b].tolist(), code / 4096, 'REPLACE')
    actual = np.zeros(len(w), np.float64)
    count = np.zeros(len(w), np.int32)
    for vertex in obj.data.vertices:
        for group in vertex.groups:
            if group.weight > 0:
                actual[vertex.index] += group.weight
                count[vertex.index] += 1
    assert np.max(abs(actual - 1)) < 1e-6 and count.min() >= 1 and count.max() <= 4
    return {'vertices': len(w), 'unweighted': int((count == 0).sum()),
            'max_influences': int(count.max()), 'max_sum_error': float(np.max(abs(actual - 1)))}


def reset(rig):
    for pb in rig.pose.bones:
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
        pb.scale = (1, 1, 1)


def rotate(rig, name, axis, degrees):
    name = named(name)
    if name not in rig.pose.bones:
        # Auxiliary skirt chains belong only to the earlier experimental rig.
        if name.startswith('skirt_'):
            return
        raise KeyError(name)
    pb = rig.pose.bones[name]
    local = pb.bone.matrix_local.to_3x3().inverted() @ Vector(axis)
    pb.rotation_quaternion = Quaternion(local, math.radians(degrees)) @ pb.rotation_quaternion


def make_actions(rig, scale):
    actions = {}
    for name, end in [('Idle_Breathe', 49), ('Walk_InPlace', 33), ('Pose_Check', 65)]:
        action = bpy.data.actions.new(name)
        action.use_fake_user = True
        rig.animation_data_create()
        rig.animation_data.action = action
        for frame in range(1, end + 1):
            reset(rig)
            phase = (frame - 1) / (end - 1) * math.tau
            if name == 'Idle_Breathe':
                rotate(rig, 'spine_02', (1, 0, 0), .7 * math.sin(phase))
                rotate(rig, 'head', (0, 0, 1), 1.5 * math.sin(phase))
            elif name == 'Walk_InPlace':
                for side, sign in [('l', 1), ('r', -1)]:
                    swing = math.sin(phase) * sign
                    rotate(rig, 'thigh_' + side, (1, 0, 0), 9 * swing)
                    rotate(rig, 'calf_' + side, (1, 0, 0), -max(0, swing) * 16)
                    rotate(rig, 'foot_' + side, (1, 0, 0), max(0, swing) * 7)
                    rotate(rig, 'upperarm_' + side, (0, 1, 0), sign * 15)
                    rotate(rig, 'upperarm_' + side, (1, 0, 0), -swing * 8)
                    rotate(rig, 'lowerarm_' + side, (1, 0, 0), 12)
                rotate(rig, 'spine_02', (0, 0, 1), 1.5 * math.sin(phase))
                rotate(rig, 'skirt_front', (1, 0, 0), -3 * abs(math.sin(phase)))
                rig.pose.bones[named('pelvis')].location.y = .003 * scale * (1 - math.cos(2 * phase))
            else:
                # Four isolated test peaks; ends rest. Not a motion-capture clip.
                peaks = [max(0, 1 - abs(frame - f) / 8) for f in [9, 25, 41, 57]]
                rotate(rig, 'upperarm_l', (0, 1, 0), -25 * peaks[0])
                rotate(rig, 'lowerarm_l', (1, 0, 0), 35 * peaks[0])
                rotate(rig, 'upperarm_r', (0, 1, 0), 25 * peaks[1])
                rotate(rig, 'lowerarm_r', (1, 0, 0), 35 * peaks[1])
                rotate(rig, 'thigh_l', (1, 0, 0), 12 * peaks[2])
                rotate(rig, 'calf_l', (1, 0, 0), -25 * peaks[2])
                rotate(rig, 'skirt_front', (1, 0, 0), -5 * peaks[2])
                rotate(rig, 'head', (0, 0, 1), 5 * peaks[3])
            for pb in rig.pose.bones:
                pb.keyframe_insert('rotation_quaternion', frame=frame, group=pb.name)
                if pb.name == named('pelvis'):
                    pb.keyframe_insert('location', frame=frame, group=pb.name)
        for curve in action.fcurves:
            for key in curve.keyframe_points:
                key.interpolation = 'LINEAR'
        actions[name] = action
    reset(rig)
    return actions


def render(scene, out, name):
    scene.render.filepath = str(out / name)
    bpy.ops.render.render(write_still=True)


def main():
    global ALIASES
    config_path, out_path = sys.argv[sys.argv.index('--') + 1:]
    config = json.loads(Path(config_path).read_text())
    source, out = Path(config['source']), Path(out_path).resolve()
    if sha(source) != config['source_sha256']:
        raise ValueError('Input has changed')
    if config['policy'] != 'purple_hair_gray_suit_skirt_v1':
        raise ValueError('Supply a reviewed case policy')
    ALIASES = config.get('aliases', {})
    out.mkdir(parents=True, exist_ok=False)
    (out / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
    shutil.copy2(__file__, out / 'rig_blender.py')
    bpy.ops.wm.open_mainfile(filepath=str(source))
    scene = bpy.context.scene
    # Fail before allocating weights or exporting a silently incomplete character.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from rig_preflight import validate_parts
    validate_parts(config, [o.name for o in scene.objects if o.type == 'MESH'])
    shutil.copy2(Path(__file__).with_name('rig_preflight.py'), out / 'rig_preflight.py')
    meshes = [bpy.data.objects[name] for name in config['parts']]
    if any(o.modifiers or o.data.shape_keys or o.vertex_groups for o in meshes):
        raise ValueError('This baseline expects static unrigged input parts')
    signatures = {o.name: signature(o) for o in meshes}
    world = {o.name: coords(o) for o in meshes}
    body, cloth = meshes
    low, high = world[body.name][:, 2].min(), world[body.name][:, 2].max()
    scale, center = (high - low) / 2, (high + low) / 2
    to_source = lambda v: (v - np.array([0, 0, center])) / scale
    canon = {name: to_source(v) for name, v in world.items()}
    bones = config['bones']
    index = {b['name']: i for i, b in enumerate(bones)}
    index.update({old: index[new] for old, new in ALIASES.items()})
    colors = base_colors(body)
    points = canon[body.name]
    hair = ((colors[:, 2] > colors[:, 1] * 1.25) & (colors[:, 0] > colors[:, 1] * 1.15)
            & (points[:, 2] > .04))
    w = skeleton_weights(points, bones)
    contact_info = None
    if config.get('hair_policy') == 'broad_hue_geodesic_contact':
        hair = ((colors[:, 2] > colors[:, 1] * 1.07) & (colors[:, 0] > colors[:, 1] * 1.04)
                & (points[:, 2] > .04))
        if config.get('hair_torso_tether'):
            posterior=(points[:,1]>.08)&(points[:,2]>.06)&(points[:,2]<.7)&(abs(points[:,0])<.29)
            hair |= posterior
        w, hair, contact_info = hair_contact_weights(body, points, hair, w, index,
                                                   torso_tether=config.get('hair_torso_tether',False))
    else:
        hair_w = np.zeros_like(w)
        t = np.clip((.78 - points[:, 2]) / .34, 0, 2)
        hair_w[:, index['head']] = np.maximum(1 - t, 0)
        hair_w[:, index['hair_01']] = np.maximum(1 - abs(t - 1), 0)
        hair_w[:, index['hair_02']] = np.clip(t - 1, 0, 1)
        w[hair] = hair_w[hair]
    w = share_seams(points, w)
    weights = {body.name: w}
    # Transfer the underlying body skin field to clothing, excluding colored hair.
    keep = np.flatnonzero(~hair)
    tree = KDTree(len(keep))
    for i in keep:
        tree.insert(Vector(points[i]), int(i))
    tree.balance()
    cw = np.zeros((len(canon[cloth.name]), len(bones)), np.float32)
    for i, point in enumerate(canon[cloth.name]):
        near = tree.find_n(Vector(point), 3)
        ids = np.array([n[1] for n in near])
        dist = np.array([n[2] for n in near])
        mix = 1 / (dist + .008) ** 2
        cw[i] = np.einsum('i,ij->j', mix / mix.sum(), w[ids])
    # Skirt follows a separate hem chain, not unrelated nearest thighs.
    p = canon[cloth.name]
    skirt = (p[:, 2] < .105) & (p[:, 2] > -.13) & (abs(p[:, 0]) < .28)
    cw[skirt] = 0
    pelvis_mix = np.clip((p[skirt, 2] + .08) / .185, 0, 1)
    angle = np.arctan2(p[skirt, 1], p[skirt, 0])
    sector = np.stack([np.maximum(np.cos(angle - a), 0) ** 2 for a in [-math.pi/2, math.pi/2, 0, math.pi]], axis=1)
    sector /= np.maximum(sector.sum(axis=1, keepdims=True), 1e-12)
    if 'skirt_front' in index:
        cw[skirt, index['pelvis']] = pelvis_mix
        for i, name in enumerate(['front', 'back', 'left', 'right']):
            cw[skirt, index['skirt_' + name]] = sector[:, i] * (1 - pelvis_mix)
    else:
        cw[skirt, index['pelvis']] = 1
    weights[cloth.name] = share_seams(p, cw)
    bpy.ops.object.select_all(action='DESELECT')
    armature = bpy.data.armatures.new('CharacterSkeleton')
    rig = bpy.data.objects.new(config.get('armature_name', 'CharacterRig'), armature)
    scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    for entry in bones:
        b = armature.edit_bones.new(entry['name'])
        b.head = Vector(np.array(entry['head']) * scale + [0, 0, center])
        b.tail = Vector(np.array(entry['tail']) * scale + [0, 0, center])
        b.use_deform = entry.get('deform', True)
        if entry['parent']:
            b.parent = armature.edit_bones[entry['parent']]
        b.align_roll(Vector(entry.get('roll_axis', (0, 0, 1) if entry['name'].startswith(('foot_', 'ball_')) else (0, 1, 0))))
    bpy.ops.object.mode_set(mode='OBJECT')
    rig.show_in_front = True
    if config.get('reference_skeleton'):
        assert {b.name: b.parent.name if b.parent else None for b in rig.data.bones} == config['reference_skeleton']['names_and_parents']
    audits = {}
    for obj in meshes:
        audits[obj.name] = assign(obj, weights[obj.name], bones)
        modifier = obj.modifiers.new('CharacterSkin', 'ARMATURE')
        modifier.object = rig
        modifier.use_deform_preserve_volume = False  # Match standard glTF/FBX linear skinning.
        matrix = obj.matrix_world.copy()
        obj.parent = rig
        obj.matrix_world = matrix
        assert signature(obj) == signatures[obj.name]
    actions = make_actions(rig, scale)
    scene.render.fps = config['animation_fps']
    scene.frame_start, scene.frame_end = 1, 65
    scene.render.resolution_x, scene.render.resolution_y = 640, 720
    scene.render.resolution_percentage = 100
    # Use the saved assembly review camera, same original materials.
    rig.animation_data.action = actions['Pose_Check']
    scene.frame_set(1)
    bpy.context.view_layer.update()
    rest_errors = {o.name: float(np.linalg.norm(coords(o, True) - world[o.name], axis=1).max()) for o in meshes}
    assert max(rest_errors.values()) < 1e-5
    motion = {}
    for action, frames in [('Pose_Check', [1, 9, 25, 41, 57, 65]), ('Walk_InPlace', [1, 9, 17, 25, 33])]:
        rig.animation_data.action = actions[action]
        motion[action] = {}
        for frame in frames:
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            entry = {}
            for obj in meshes:
                deformed = coords(obj, True)
                assert np.isfinite(deformed).all()
                displacements = np.linalg.norm(deformed - world[obj.name], axis=1)
                entry[obj.name] = {'max_displacement_m': float(displacements.max()),
                                   'mean_displacement_m': float(displacements.mean())}
            motion[action][str(frame)] = entry
            if action == 'Pose_Check':
                render(scene, out, f'pose-{frame:03d}.png')
    for obj in meshes:
        assert max(x[obj.name]['max_displacement_m'] for x in motion['Walk_InPlace'].values()) > .01
    frames_dir = out / 'walk-frames'
    frames_dir.mkdir()
    rig.animation_data.action = actions['Walk_InPlace']
    for frame in range(1, 33):
        scene.frame_set(frame)
        render(scene, frames_dir, f'{frame:04d}.png')
    rig.animation_data.action = actions['Pose_Check']
    scene.frame_set(1)
    textures = out / 'textures'
    textures.mkdir()
    for i, image in enumerate(bpy.data.images):
        if image.packed_file:
            path = textures / f'texture-{i:02d}.jpg'
            path.write_bytes(bytes(image.packed_file.data))
            image.filepath_raw = str(path)
    bpy.ops.object.select_all(action='DESELECT')
    rig.select_set(True)
    for obj in meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.wm.save_as_mainfile(filepath=str(out / 'character-rigged.blend'))
    bpy.ops.export_scene.gltf(filepath=str(out / 'character-rigged.glb'), export_format='GLB',
        use_selection=True, export_normals=False, export_skins=True, export_animations=True,
        export_animation_mode='ACTIONS', export_influence_nb=4, export_all_influences=False)
    bpy.ops.export_scene.fbx(filepath=str(out / 'character-rigged.fbx'), use_selection=True,
        object_types={'ARMATURE', 'MESH'}, add_leaf_bones=False, bake_anim=True,
        bake_anim_use_all_actions=True, bake_anim_use_nla_strips=False, bake_anim_simplify_factor=0,
        path_mode='COPY', embed_textures=True, use_mesh_modifiers=False)
    assert sha(source) == config['source_sha256']
    report = {'source_sha256': config['source_sha256'], 'blender': bpy.app.version_string,
        'bone_count': len(bones), 'bone_names': [b['name'] for b in bones], 'weights': audits,
        'reference_skeleton': config.get('reference_skeleton'), 'hair_contact_policy': contact_info,
        'source_signatures': signatures, 'rest_pose_max_error_m': rest_errors,
        'motion': motion, 'actions': list(actions), 'hair_mask_vertices': int(hair.sum()),
        'skirt_mask_vertices': int(skirt.sum()), 'geometry_unchanged': True,
        'checks': {'rig_created': 'pass', 'normalized_skin_weights': 'pass', 'rest_geometry_preserved': 'pass',
            'actual_mesh_deformation': 'pass', 'visual_animation_review': 'not_run',
            'export_roundtrip': 'not_run', 'engine': 'not_run', 'global_collision_free': 'unknown'},
        'limitations': ['Case-specific joints and color policy; not universal autorig',
            'Procedural diagnostic clips, not motion capture or polished gait',
            'Finger chains follow reference when supplied; grasp fidelity is unverified',
            'No facial controls, cloth simulation or hair dynamics', 'Missing shoes'],
        'output_sha256': {name: sha(out / name) for name in ['character-rigged.blend','character-rigged.glb','character-rigged.fbx']}}
    (out / 'rig-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('RIG_CREATED', report['bone_count'], report['actions'])


if __name__ == '__main__':
    main()
