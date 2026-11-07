"""Material-only behavior on synthetic meshes, including shared data and bad masks."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HELPER = Path(__file__).resolve().parents[1]/'workspace/.agents/skills/character-material-refinement/scripts/material_edit.py'


@unittest.skipUnless(os.environ.get('BLENDER_BIN'), 'Set BLENDER_BIN for Blender integration')
class MaterialEditTests(unittest.TestCase):
    def test_scoped_regions_shared_data_and_preflight(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory);script = root/'test.py'
            script.write_text('''import bpy, runpy, json, hashlib, numpy as np
from pathlib import Path
helper=runpy.run_path(HELPER)
root=Path(ROOT)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add();obj=bpy.context.object;obj.name='RobotShell'
mat=bpy.data.materials.new('SharedCoating');mat.use_nodes=True;mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.73
obj.data.materials.append(mat)
other=bpy.data.objects.new('ProtectedShell',obj.data);bpy.context.collection.objects.link(other)
original_mesh=other.data;original_color=tuple(mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value)
sig=helper['fingerprint'](obj)
def mask(name, faces):
 p=root/(name+'.json');p.write_text(json.dumps(faces));return {'path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def region(name, faces):
 return {'name':name,'object':obj.name,'mesh_sha256':sig,'faces':mask(name,faces),'color_srgb':[.2,.4,.6],'color_evidence':'Synthetic fixture swatch, no anatomy assumption'}
def run(regions, name):
 p=root/(name+'.json');p.write_text(json.dumps({'regions':regions}));out=root/name;out.mkdir();return helper['apply'](p,out)
# A valid first region followed by an invalid region must not partially edit.
a=region('one',[0]);bad=region('two',[99])
try:run([a,bad],'bad-range');raise AssertionError('Invalid mask accepted')
except ValueError:pass
assert obj.data==original_mesh and len(bpy.data.materials)==1
bad=dict(a, mesh_sha256='0'*64)
try:run([bad],'stale');raise AssertionError('Stale fingerprint accepted')
except ValueError:pass
try:run([a,region('overlap',[0,1])],'overlap');raise AssertionError('Overlapping masks accepted')
except ValueError:pass
bad=dict(a,faces=dict(a['faces'],sha256='0'*64))
try:run([bad],'tampered');raise AssertionError('Tampered mask accepted')
except ValueError:pass
result=run([a,region('another',[2])],'success')
assert result['status']=='pass'
assert obj.data!=original_mesh and other.data==original_mesh
assert all(p.material_index==0 for p in other.data.polygons)
assert [p.material_index for p in obj.data.polygons]==[1,0,2,0,0,0]
assert helper['fingerprint'](obj)==sig==helper['fingerprint'](other)
assert tuple(mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value)==original_color
for slot in [1,2]:
 s=obj.data.materials[slot].node_tree.nodes['Principled BSDF'];assert abs(s.inputs['Roughness'].default_value-.73)<1e-6
 np.testing.assert_allclose(s.inputs['Base Color'].default_value[:3],[.0331047666,.1328683216,.3185467781],atol=1e-6)
assert (root/'success/material-inputs/one-faces.json').exists()
# Native save/reload retains exact protected mesh signature and scoped slots.
bpy.ops.wm.save_as_mainfile(filepath=str(root/'edited.blend'))
bpy.ops.wm.open_mainfile(filepath=str(root/'edited.blend'))
assert helper['fingerprint'](bpy.data.objects['RobotShell'])==sig
assert all(p.material_index==0 for p in bpy.data.objects['ProtectedShell'].data.polygons)
'''.replace('HELPER', repr(str(HELPER))).replace('ROOT', repr(str(root))))
            result = subprocess.run([os.environ['BLENDER_BIN'],'-b','--factory-startup','--python-exit-code','1','--python',str(script)],capture_output=True,text=True,timeout=90)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)

if __name__ == '__main__':unittest.main()
