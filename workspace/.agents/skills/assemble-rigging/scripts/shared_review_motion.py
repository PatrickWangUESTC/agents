"""Generate the shared four-event review motion from a static project rig."""
from pathlib import Path
import math, sys, bpy
from mathutils import Vector, Quaternion, Matrix
out = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
if out.exists() or out.suffix.lower() != '.blend':
    raise ValueError('Choose a new .blend output path')
out.parent.mkdir(parents=True, exist_ok=True)
scene=bpy.context.scene
rig=scene.objects['HumanArmature']
rig.animation_data_clear()
for bone in rig.pose.bones:
    bone.matrix_basis = Matrix.Identity(4)
hip=rig.pose.bones['DEF-Hips']
height=scene.objects['body'].dimensions.z
# Derive the horizontal axes from the current skeleton.
side_axis=rig.data.bones['DEF-Left ankle'].head_local-rig.data.bones['DEF-Right ankle'].head_local
lateral=Vector((side_axis.x,side_axis.y,0)).normalized()
up=Vector((0,0,1))
forward=lateral.cross(up).normalized()
def rotate(name, axis, degrees, frame):
    b=rig.pose.bones[name]
    basis=b.bone.matrix_local.to_quaternion()
    b.rotation_mode='QUATERNION'
    b.rotation_quaternion=basis.inverted()@Quaternion(axis,math.radians(degrees))@basis
    b.keyframe_insert(data_path='rotation_quaternion',frame=frame)
def pulse(f,mid,width):
    return math.cos((f-mid)*math.pi/(2*width))**2 if abs(f-mid)<width else 0
end=105
# Project the rest toe direction into the horizontal sagittal plane.
toe=rig.data.bones['DEF-Left toe'].head_local-rig.data.bones['DEF-Left ankle'].head_local
travel=toe-lateral*toe.dot(lateral)-up*toe.dot(up)
travel.normalize()
for f in range(1,end+1):
    phases=[max(0,min(1,(f-start)/20)) for start in (20,62)]
    flight=sum(4*t*(1-t) for t in phases)
    spread=sum(math.sin(math.pi*t)**2 for t in phases)
    squat=sum(pulse(f,center,5) for center in (15,45,57,87))
    sweep=pulse(f,29,13)-pulse(f,45,12)-pulse(f,71,13)+pulse(f,87,12)
    yaw=46*(pulse(f,30,16)-pulse(f,72,16))
    def keyed(name,q):
        bone=rig.pose.bones[name]
        basis=bone.bone.matrix_local.to_quaternion()
        bone.rotation_mode='QUATERNION'
        bone.rotation_quaternion=basis.inverted()@q@basis
        bone.keyframe_insert(data_path='rotation_quaternion',frame=f)
    for side,sign in [('Left',1),('Right',-1)]:
        keyed('DEF-'+side+' leg',Quaternion(forward,math.radians(sign*48*spread))@Quaternion(lateral,math.radians(42*squat)))
        rotate('DEF-'+side+' knee',lateral,-83*squat,f)
        rotate('DEF-'+side+' ankle',lateral,41*squat,f)
        keyed('DEF-'+side+' arm',Quaternion(forward,math.radians(sign*(13+15*spread)+35*sweep))@Quaternion(lateral,math.radians(-16)))
    rotate('DEF-Neck',up,yaw*.35,f)
    rotate('DEF-Head',up,yaw*.65,f)
    hip.location=Vector((0,0,0))
    hip.keyframe_insert(data_path='location',frame=f)
    scene.frame_set(f)
    ankle=rig.pose.bones['DEF-Left ankle']
    compression=ankle.bone.head_local.z-ankle.head.z if squat else 0
    distance=(phases[0]-phases[1])*.54*height
    hip.location=hip.bone.matrix_local.to_quaternion().inverted()@(travel*distance+up*(height*.23*flight+compression))
    hip.keyframe_insert(data_path='location',frame=f)

# Open into a split stance during the descending half of the second jump.
for f in range(73,106):
    scene.frame_set(f)
    u=min(1.,(f-72)/10)
    blend=u*u*(3-2*u)
    settle=pulse(f,87,5)
    drop=height*(.12+.035*settle)
    loc=hip.location.copy()
    hip.location=loc.lerp(hip.bone.matrix_local.to_quaternion().inverted()@(-up*drop),blend)
    hip.keyframe_insert(data_path='location',frame=f)
    for side,sign in [('Left',1),('Right',-1)]:
        bones=[rig.pose.bones['DEF-'+side+' '+n] for n in ('leg','knee','ankle')]
        a,k,e=[b.bone.head_local.copy() for b in bones]
        start=a-up*drop
        dest=e+sign*.285*height*travel
        axis=(dest-start).normalized()
        l1=(k-a).length;l2=(e-k).length
        dist=min((dest-start).length,l1+l2-1e-8)
        along=(dist*dist+l1*l1-l2*l2)/(2*dist)
        pole=(travel-axis*travel.dot(axis)).normalized()
        knee=start+axis*along+pole*math.sqrt(max(0,l1*l1-along*along))
        thigh=(k-a).rotation_difference(knee-start)
        shin=(thigh@(e-k)).rotation_difference(dest-knee)@thigh
        for b,q in zip(bones,(thigh,thigh.inverted()@shin,shin.inverted())):
            basis=b.bone.matrix_local.to_quaternion()
            b.rotation_quaternion=b.rotation_quaternion.slerp(basis.inverted()@q@basis,blend)
            b.keyframe_insert(data_path='rotation_quaternion',frame=f)

rig.animation_data.action.name = 'Shared rigging review'
scene.frame_start, scene.frame_end = 1, end
scene.render.fps, scene.render.fps_base = 30, 1
for name, frame in [('Forward jump', 30), ('Landing', 45), ('Backward jump', 72), ('Split stance', 87)]:
    previous = scene.timeline_markers.get(name)
    if previous:
        scene.timeline_markers.remove(previous)
    scene.timeline_markers.new(name, frame=frame)
scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True)
