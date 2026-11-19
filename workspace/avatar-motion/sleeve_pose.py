"""Bake a damped, length-constrained sleeve pendulum in world space."""
import math
import bpy
from mathutils import Vector, Quaternion

DOWN = Vector((0, 0, -1))
SETTINGS = {
    'sleeve_gravity': (9.8, 0., 30., 'Downward acceleration in Blender units per second squared'),
    'sleeve_drag': (7.0, 0., 30., 'Velocity damping per second'),
    'sleeve_root_support': (.23, 0., 1., 'Rest-direction force as a fraction of gravity at the sleeve root'),
    'sleeve_tip_support': (.055, 0., 1., 'Rest-direction force as a fraction of gravity at the sleeve tip'),
}


def pose_sleeve(bone, frame, previous):
    rig = bone.id_data
    for name, (value, low, high, description) in SETTINGS.items():
        if name not in rig:
            rig[name] = value
            rig.id_properties_ui(name).update(min=low, max=high, description=description)

    scene = bpy.context.scene
    dt = scene.render.fps_base / scene.render.fps
    world = rig.matrix_world
    parent = bone.parent
    parent_rotation = world.to_quaternion() @ parent.matrix.to_quaternion() @ parent.bone.matrix_local.to_quaternion().inverted()
    rest = (bone.bone.tail_local-bone.bone.head_local).normalized()
    preferred = (parent_rotation @ rest).normalized()
    anchor = world @ bone.head
    length = (world.to_3x3() @ (bone.bone.tail_local-bone.bone.head_local)).length
    tip = bone.name.startswith('SleeveTip')
    support = rig['sleeve_tip_support' if tip else 'sleeve_root_support']
    force = (DOWN + preferred*support)*rig['sleeve_gravity']
    state = previous.get(bone.name)
    if state is None or state[0] != frame-1:
        direction = force.normalized() if force.length else preferred
        pos = direction*length
        velocity = Vector((0,0,0))
        old_anchor = anchor
        old_speed = Vector((0,0,0))
        old_q = None
    else:
        _, old_anchor, old_speed, pos, velocity, old_q = state
    # Solve the link in a translating anchor frame with world-oriented axes.
    # Air drag damps swing; constant character travel must not lift the fabric.
    speed=(anchor-old_anchor)/dt
    acceleration=(speed-old_speed)/dt
    inertia=acceleration*.45
    limit=.75*rig['sleeve_gravity']
    if inertia.length>limit:
        inertia=inertia.normalized()*limit
    force-=inertia
    steps = max(1, math.ceil(dt*180))
    h = dt/steps
    for i in range(steps):
        velocity = velocity*math.exp(-rig['sleeve_drag']*h)+force*h
        predicted = pos+velocity*h
        axis = predicted
        if axis.length < 1e-8:
            axis = preferred
        corrected = axis.normalized()*length
        velocity = (corrected-pos)/h
        pos = corrected
    direction = parent_rotation.inverted() @ pos.normalized()
    swing = rest.rotation_difference(direction)
    basis = bone.bone.matrix_local.to_quaternion()
    local = basis.inverted() @ swing @ basis
    if old_q is not None:
        local.make_compatible(old_q)
    bone.rotation_mode = 'QUATERNION'
    bone.rotation_quaternion = local
    bone.keyframe_insert(data_path='rotation_quaternion', frame=frame)
    previous[bone.name] = (frame,anchor.copy(),speed.copy(),pos.copy(),velocity.copy(),local.copy())
