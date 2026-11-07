"""Synthetic character fixture; no production character or quality claims."""
import bpy,json,hashlib,sys
from pathlib import Path
root=Path(sys.argv[sys.argv.index('--')+1]); root.mkdir(parents=True,exist_ok=True)

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name):
    p=root/name; bpy.ops.wm.save_as_mainfile(filepath=str(p));return {'path':str(p),'sha256':sha(p)}
def cube(name,loc,scale):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc)
    o=bpy.context.object;o.name=name;o.scale=scale
    mat=bpy.data.materials.new(name+'Material');mat.diffuse_color=(.4,.2,.6,1);o.data.materials.append(mat)
    return o
bpy.ops.wm.read_factory_settings(use_empty=True)
cube('Body',(0,0,1),(.5,.3,1))
cube('Clothing',(0,0,.8),(.65,.4,.5))
cube('HeadOld',(0,0,1.8),(.35,.35,.35))
cube('ShoeLeft',(-.3,-.1,.1),(.2,.4,.2));cube('ShoeRight',(.3,-.1,.1),(.2,.4,.2))
source=save('source.blend')
bpy.ops.wm.read_factory_settings(use_empty=True)
cube('HeadNew',(0,0,1.8),(.4,.38,.4)); candidate=save('head.blend')
config={'source':source,'candidate':{**candidate,'objects':['HeadNew']},'targets':['HeadOld'],
 'placements':{'HeadNew':[[.4,0,0,0],[0,.38,0,0],[0,0,.4,1.8],[0,0,0,1]]}}
(root/'upgrade.json').write_text(json.dumps(config))
bones=[{'name':'root','parent':None,'head':[0,0,.2],'tail':[0,0,1.5]},
 {'name':'head','parent':'root','head':[0,0,1.5],'tail':[0,0,2]},
 {'name':'foot_l','parent':'root','head':[-.3,0,.1],'tail':[-.3,-.4,.1]},
 {'name':'foot_r','parent':'root','head':[.3,0,.1],'tail':[.3,-.4,.1]}]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.object.armature_add();r=bpy.context.object;r.name='ReferenceRig';bpy.ops.object.mode_set(mode='EDIT')
for b in list(r.data.edit_bones):r.data.edit_bones.remove(b)
for b in bones:
    bone=r.data.edit_bones.new(b['name']);bone.head=b['head'];bone.tail=b['tail']
for b in bones:
    if b['parent']:r.data.edit_bones[b['name']].parent=r.data.edit_bones[b['parent']]
bpy.ops.object.mode_set(mode='OBJECT');reference=save('reference.blend')
(root/'bones.json').write_text(json.dumps(bones));(root/'reference.json').write_text(json.dumps({**reference,'object':'ReferenceRig'}))
(root/'body-weights.json').write_text(json.dumps([{'root':1.} for _ in range(8)]))
