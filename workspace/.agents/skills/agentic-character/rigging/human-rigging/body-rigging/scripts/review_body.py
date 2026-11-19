"""Blender -b body.blend -P review_body.py -- NEW_REVIEW_DIRECTORY"""
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile

import bpy
import numpy as np
from mathutils import Matrix, Vector, Quaternion

toolkit = Path.home()/'.codex/skills/avatar-rigging/scripts'
sys.path.insert(0,str(toolkit))
from diagnostic_run import author
from motion_extrema import select_frames
from four_view import render_four_views


def coordinates(obj):
    return np.array([obj.matrix_world @ v.co for v in obj.data.vertices])


def surface(obj):
    return coordinates(obj.evaluated_get(bpy.context.evaluated_depsgraph_get()))


def main(out):
    out.mkdir(parents=True,exist_ok=False)
    src = Path(bpy.data.filepath)
    body = bpy.context.scene.objects['body']
    rig = body.find_armature()
    if not rig or len(rig.data.bones)!=58:
        raise ValueError('Expected a 58-bone body')
    rows = [{body.vertex_groups[g.group].name:g.weight for g in v.groups
             if g.weight>0 and body.vertex_groups[g.group].name in rig.data.bones} for v in body.data.vertices]
    if any(len(row)>4 or abs(sum(row.values())-1)>1e-5 for row in rows):
        raise ValueError('Invalid bone weights')
    # Align the scratch scene to the diagnostic authoring tool (+X left, +Z up).
    def joint(name):
        return rig.matrix_world @ rig.data.bones['DEF-'+name].head_local
    x = (joint('Left arm')-joint('Right arm')).normalized()
    up = joint('Neck')-joint('Hips')
    z = (up-x*up.dot(x)).normalized()
    if body.parent!=rig: raise ValueError('Align body and rig together before review')
    rig.matrix_world = Matrix([x,z.cross(x),z]).to_4x4() @ rig.matrix_world
    bpy.context.view_layer.update()
    rest = coordinates(body)
    height = float(np.ptp(rest[:,2]))
    rig_name = rig.name
    mapping = dict(armature=rig_name,hips='DEF-Hips',head='DEF-Head')
    joints = dict(pelvis='DEF-Hips',chest='DEF-Upper Chest',head='DEF-Head')
    finger_tests = []
    for side in ('Left','Right'):
        names = ['DEF-'+side+' '+n for n in ('leg','knee','ankle','arm','elbow','wrist')]
        mapping[side.lower()] = dict(zip(('thigh','shin','foot','upper_arm','forearm','hand'),names))
        joints.update({side.lower()+'_'+role:name for role,name in zip(('hip','knee','foot','shoulder','elbow'),names)})
        # Landmark probes are selected by rest surface proximity rather than existing weights.
        suffix = '_'+side[0]
        digits = ['Thumb','IndexFinger','MiddleFinger','RingFinger','LittleFinger']
        tips = []
        for digit in digits:
            last = rig.data.bones['DEF-'+digit+('2' if digit=='Thumb' else '3')+suffix]
            tips.append(np.argsort(np.linalg.norm(rest-np.array(rig.matrix_world@last.tail_local),axis=1))[:3])
        for i,digit in enumerate(digits):
            pb = rig.pose.bones['DEF-'+digit+'1'+suffix]
            saved = pb.matrix_basis.copy()
            pb.rotation_quaternion = Quaternion((1,0,0),math.radians(40))
            bpy.context.view_layer.update()
            delta = np.linalg.norm(surface(body)-rest,axis=1)
            motion = [float(np.median(delta[idx])/height) for idx in tips]
            pb.matrix_basis=saved
            bpy.context.view_layer.update()
            finger_tests.append(dict(bone=pb.name,tip_vertex_ids=[a.tolist() for a in tips],
                                     own=motion[i],other_max=max(motion[:i]+motion[i+1:]),tip_displacements=motion))
    with tempfile.TemporaryDirectory() as tmp:
        neutral=Path(tmp)/'neutral.blend'
        bpy.ops.wm.save_as_mainfile(filepath=str(neutral),copy=True)
        author(neutral,mapping,out/'run.blend')
    bpy.ops.wm.open_mainfile(filepath=str(out/'run.blend'))
    scene=bpy.context.scene
    rig=scene.objects[rig_name]
    body=scene.objects['body']
    extrema=select_frames(scene,rig,joints)
    edges=np.array([e.vertices[:] for e in body.data.edges])
    length=np.linalg.norm(rest[edges[:,0]]-rest[edges[:,1]],axis=1)
    edges=edges[length>height*1e-5]
    length=length[length>height*1e-5]
    stats=[]
    for frame in range(1,25):
        scene.frame_set(frame)
        p=surface(body)
        ratio=np.linalg.norm(p[edges[:,0]]-p[edges[:,1]],axis=1)/length
        def describe(j):
            ids=edges[j].tolist()
            return dict(vertices=ids,weights=[rows[i] for i in ids],ratio=float(ratio[j]))
        stats.append(dict(frame=frame,p99=float(np.percentile(ratio,99)),p01=float(np.percentile(ratio,1)),
                          longest=describe(np.argmax(ratio)),shortest=describe(np.argmin(ratio))))
    worst=max(stats,key=lambda row:row['longest']['ratio'])
    shortest=min(stats,key=lambda row:row['shortest']['ratio'])
    frames=sorted(set(extrema['frames']+[worst['frame'],shortest['frame']]))
    framing=dict(center=((rest.max(0)+rest.min(0))/2).tolist(),ortho_scale=height*1.5,distance=height*4)
    for frame in frames:
        scene.frame_set(frame)
        render_four_views(scene,out/f'f{frame:02}',objects=[body],tile=(192,240),samples=2,
                          save_views=False,framing=framing)
    report=dict(source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),frames=frames,
                extrema=extrema['events'],metric_by_frame=stats,finger_landmarks=finger_tests)
    (out/'report.json').write_text(json.dumps(report,indent=2))


if __name__=='__main__':
    main(Path(sys.argv[-1]).resolve())
