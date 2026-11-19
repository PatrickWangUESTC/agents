"""Replay the reviewed body and camera actions and bake current hair/sleeve chains."""
from pathlib import Path
import bpy, sys, math
from mathutils import Vector, Quaternion

def swing_hair(b, frame, dt, state):
    parent=b.parent
    rotation=parent.matrix.to_quaternion()@parent.bone.matrix_local.to_quaternion().inverted()
    axis=(b.bone.tail_local-b.bone.head_local).normalized()
    preferred=rotation@axis
    target=b.head+preferred*b.length
    root=parent.name=='DEF-Head'
    stiffness=115 if root else 68
    previous,velocity=state.get(b.name,(target.copy(),Vector((0,0,0))))
    start=state.get((b.name,'target'),target)
    steps=max(1,math.ceil(dt*150))
    h=dt/steps
    for j in range(steps):
        goal=start.lerp(target,(j+1)/steps)
        velocity+=((goal-previous)*stiffness-velocity*(12 if root else 8)+Vector((0,0,-.16)))*h
        previous+=velocity*h
    offset=previous-target
    swing=preferred.rotation_difference((preferred*b.length+offset).normalized())
    limit=math.radians(12 if root else 19)
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
for c in list(action.fcurves):
    if any(k in c.data_path for k in ('bones["Hair.','bones["Sleeve')): action.fcurves.remove(c)
r.animation_data_create().action=action
s.camera.animation_data_create().action=camera_action
s.frame_start=1;s.frame_end=90;s.render.fps=15;s.render.fps_base=1
sys.path.insert(0,str(Path(__file__).resolve().parents[4]/'avatar-motion'))
from sleeve_pose import pose_sleeve
bones=sorted([b for b in r.pose.bones if b.name.startswith(('Hair.','Sleeve'))],key=lambda b:len(b.parent_recursive))
hair_state={};sleeve_state={}
for f in range(1,91):
    s.frame_set(f)
    for b in bones:
        bpy.context.view_layer.update()
        if b.name.startswith('Hair.'):swing_hair(b,f,1/15,hair_state)
        else:pose_sleeve(b,f,sleeve_state)
s.frame_set(1)
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(out))
