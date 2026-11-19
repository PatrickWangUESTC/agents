"""Blender: -b source.blend -P apply_hair.py -- guides.json output.blend"""
import bpy,json,os,sys,subprocess,tempfile
import numpy as np
from pathlib import Path
from mathutils import Vector,Quaternion
spec,out=map(lambda a:Path(a).resolve(),sys.argv[-2:])
s=bpy.context.scene;r=s.objects['HumanArmature'];o=next(o for o in s.objects if o.name in ('hair','hair-ornaments'))
def points(obj):return np.array([obj.matrix_world@v.co for v in obj.data.vertices])
before=points(o.evaluated_get(bpy.context.evaluated_depsgraph_get()))
with tempfile.TemporaryDirectory() as tmp:
    src=Path(tmp)/'mesh.npz';result=Path(tmp)/'weights.npz'
    np.savez(src,vertices=points(o),edges=np.array([e.vertices[:] for e in o.data.edges]))
    subprocess.run([os.environ['RIG_SCIPY_PYTHON'],str(Path(__file__).with_name('fit_hair.py')),str(src),str(spec),str(result)],check=True)
    data=np.load(result);bones=json.loads(str(data['bones']));names=data['names'].tolist();w=data['weights']
bpy.context.view_layer.objects.active=r;r.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
for b in list(r.data.edit_bones):
    if b.name.startswith('Hair.'):r.data.edit_bones.remove(b)
inv=r.matrix_world.inverted()
for row in bones:
    b=r.data.edit_bones.new(row['name']);b.head=inv@Vector(row['head']);b.tail=inv@Vector(row['tail']);b.parent=r.data.edit_bones[row['parent']]
    if b.parent.name!='DEF-Head' and (b.head-b.parent.tail).length<1e-5:b.use_connect=True
bpy.ops.object.mode_set(mode='OBJECT')
for g in list(o.vertex_groups):
    if g.name.startswith('Hair.') or g.name=='DEF-Head':o.vertex_groups.remove(g)
groups=[o.vertex_groups.new(name=n) for n in names]
for i,row in enumerate(w):
    ix=np.argsort(row)[-4:];total=row[ix].sum()
    for j in ix:
        if row[j]>1e-8:groups[j].add([i],float(row[j]/total),'REPLACE')
bpy.context.view_layer.update()
assert np.max(abs(points(o.evaluated_get(bpy.context.evaluated_depsgraph_get()))-before))<1e-5
r.show_in_front=True
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(out))
bpy.ops.wm.open_mainfile(filepath=str(out))
s=bpy.context.scene;r=s.objects['HumanArmature'];o=next(o for o in s.objects if o.name in ('hair','hair-ornaments'))
old=points(o.evaluated_get(bpy.context.evaluated_depsgraph_get()));checks={}
for guide in json.loads(spec.read_text()):
    label='Hair.'+guide['name']+'.'+str(len(guide['points'])-1);b=r.pose.bones[label]
    b.rotation_quaternion=Quaternion((1,0,0),.55);bpy.context.view_layer.update()
    delta=np.linalg.norm(points(o.evaluated_get(bpy.context.evaluated_depsgraph_get()))-old,axis=1)
    checks[label]=float(delta.max());assert checks[label]>1e-5,label
    b.rotation_quaternion.identity();bpy.context.view_layer.update()
out.with_suffix('.json').write_text(json.dumps(dict(bones=bones,isolated_tip_displacement=checks),indent=2))
