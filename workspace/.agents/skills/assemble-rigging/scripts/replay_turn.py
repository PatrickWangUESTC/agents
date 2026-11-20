"""Replay the reviewed body and camera actions and bake current hair, sleeve and skirt chains."""
from pathlib import Path
import bpy, sys, math
from mathutils import Vector, Quaternion

def skirt_profiles(rig, body_height):
    """Derive each skirt spring from rest length and distance below its fixed root."""
    profiles = {}
    bones = [b for b in rig.pose.bones if b.name.startswith('Skirt.')]
    for b in bones:
        if b.parent and b.parent.name.startswith('Skirt.'):
            continue
        chain = [b]
        while True:
            children = [c for c in chain[-1].children if c.name.startswith('Skirt.')]
            if not children:
                break
            if len(children) != 1:
                raise ValueError(f"Expected a linear skirt chain at {chain[-1].name}")
            chain.append(children[0])
        lengths = [(rig.matrix_world.to_3x3() @ (c.bone.tail_local - c.bone.head_local)).length for c in chain]
        factor = math.sqrt(.43 * body_height / sum(lengths))
        distance = 0.
        for c, length in zip(chain, lengths):
            depth = distance / sum(lengths[:-1]) if len(chain) > 1 else 0.
            hz = min(3.64, max(1.78, (3.50 - 1.55 * depth) * factor))
            ratio = .83 - .18 * depth
            degrees = 9 + 19 * depth
            profiles[c.name] = (hz, ratio, degrees)
            c.bone['frequency_hz'], c.bone['damping_ratio'], c.bone['angular_limit_deg'] = profiles[c.name]
            distance += length
    return profiles


def swing_chain(b, frame, dt, state, skirt=None):
    parent=b.parent
    rotation=parent.matrix.to_quaternion()@parent.bone.matrix_local.to_quaternion().inverted()
    axis=(b.bone.tail_local-b.bone.head_local).normalized()
    preferred=rotation@axis
    target=b.head+preferred*b.length
    root=parent.name=='DEF-Head'
    stiffness=115 if root else 68
    drag=12 if root else 8
    limit=math.radians(12 if root else 19)
    if skirt is not None:
        hz,ratio,degrees=skirt
        omega=2*math.pi*hz
        stiffness=omega**2
        drag=2*ratio*omega
        limit=math.radians(degrees)
    previous,velocity=state.get(b.name,(target.copy(),Vector((0,0,0))))
    start=state.get((b.name,'target'),target)
    steps=max(1,math.ceil(dt*150))
    h=dt/steps
    for j in range(steps):
        goal=start.lerp(target,(j+1)/steps)
        velocity+=((goal-previous)*stiffness-velocity*drag+Vector((0,0,-.16)))*h
        previous+=velocity*h
    offset=previous-target
    swing=preferred.rotation_difference((preferred*b.length+offset).normalized())
    if swing.angle>limit:swing=Quaternion().slerp(swing,limit/swing.angle)
    q=axis.rotation_difference(rotation.inverted()@(swing@preferred))
    basis=b.bone.matrix_local.to_quaternion()
    q=basis.inverted()@q@basis
    last=state.get((b.name,'q'))
    if last is not None:q.make_compatible(last)
    b.rotation_mode='QUATERNION';b.rotation_quaternion=q
    b.keyframe_insert(data_path='rotation_quaternion',frame=frame)
    state[b.name]=(previous,velocity);state[b.name,'target']=target.copy();state[b.name,'q']=q.copy()

source,out=map(lambda x:Path(x).resolve(),sys.argv[-2:])
s=bpy.context.scene;r=s.objects['HumanArmature']
with bpy.data.libraries.load(str(source)) as (src,dst):
    dst.actions=['Pirouette - body and secondary motion','Camera.001Action']
action,camera_action=dst.actions
skirt = skirt_profiles(r,s.objects['body'].dimensions.z) if any(b.name.startswith('Skirt.') for b in r.pose.bones) else {}
for c in list(action.fcurves):
    if any(k in c.data_path for k in ('bones["Hair.','bones["Sleeve')) or (skirt and 'bones["Skirt.' in c.data_path): action.fcurves.remove(c)
r.animation_data_create().action=action
s.camera.animation_data_create().action=camera_action
s.frame_start=1;s.frame_end=90;s.render.fps=15;s.render.fps_base=1
sys.path.insert(0,str(Path(__file__).resolve().parents[4]/'avatar-motion'))
from sleeve_pose import pose_sleeve
bones=sorted([b for b in r.pose.bones if b.name.startswith(('Hair.','Sleeve','Skirt.'))],key=lambda b:len(b.parent_recursive))
hair_state={};sleeve_state={}
for f in range(1,91):
    s.frame_set(f)
    for b in bones:
        bpy.context.view_layer.update()
        if b.name in skirt:swing_chain(b,f,1/15,hair_state,skirt[b.name])
        elif b.name.startswith('Hair.'):swing_chain(b,f,1/15,hair_state)
        else:pose_sleeve(b,f,sleeve_state)
s.frame_set(1)
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(out))
