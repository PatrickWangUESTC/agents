"""File-bound decisions and a real Blender observe/edit/verify/review loop."""
import importlib.util, os, subprocess, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'workspace/.agents/skills/three-d-ai-lab/scripts/lab.py'
spec=importlib.util.spec_from_file_location('loop_lab',SCRIPT);lab=importlib.util.module_from_spec(spec);spec.loader.exec_module(lab)

class LoopPacketTests(unittest.TestCase):
 def setUp(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name);self.rev=self.root/'revisions/r0000';self.rev.mkdir(parents=True)
  lab.write(self.root/'case.json',{'assets':[],'required_checks':['fixture_translation']})
  for n in ['scene.blend','front.png','execution.log']:(self.rev/n).write_text('fixture only')
  lab.write(self.rev/'inventory.json',{'objects':{}});lab.write(self.rev/'checks.json',{'native_readback':'pass'})
  lab.write(self.rev/'receipt.json',{'revision':'r0000','status':'produced','acceptance':'not_run','files':{p.name:lab.digest(p) for p in self.rev.iterdir()}})
  lab.write(self.root/'session.json',{'selected':'r0000','latest':'r0000','case_sha256':lab.digest(self.root/'case.json')})
  self.packet=self.root/'observation.json';lab.write(self.packet,lab.observe(self.root))
  self.op=self.root/'operation.py';self.op.write_text('# fixture only')
  self.decision={'observation':str(self.packet),'observation_sha256':lab.digest(self.packet),'operation':str(self.op),'operation_sha256':lab.digest(self.op),'diagnosis':'fixture','edit_scope':'fixture','expected_improvement':'fixture','stop_condition':'fixture','viewed_images':[str(self.rev/'front.png')]}
 def act(self):
  path=self.root/'decision.json';lab.write(path,self.decision)
  with patch.object(lab,'run_revision',return_value={'status':'produced'}) as execute:
   result=lab.act(self.root,path);self.assertTrue(execute.called);return result
 def test_action_input_frozen(self):
  self.assertEqual(self.act()['status'],'produced');a=list((self.root/'actions').iterdir());self.assertEqual(len(a),1);self.assertEqual((a[0]/'operation.py').read_text(),'# fixture only')
 def test_changed_selection_rejected(self):
  state=lab.read(self.root/'session.json');state['selected']='r0001';lab.write(self.root/'session.json',state)
  with self.assertRaisesRegex(ValueError,'Selected checkpoint changed'):self.act()
 def test_changed_packet_and_script_rejected(self):
  self.packet.write_text(self.packet.read_text()+' ')
  with self.assertRaisesRegex(ValueError,'packet changed'):self.act()
  self.decision['observation_sha256']=lab.digest(self.packet);self.op.write_text('# changed')
  with self.assertRaisesRegex(ValueError,'Operation changed'):self.act()
 def test_image_evidence_required(self):
  self.decision['viewed_images']=[]
  with self.assertRaisesRegex(ValueError,'current observed images'):self.act()
 def test_geometry_spec(self):
  for s in [{},{'surface_pairs':[]},{'surface_pairs':[{'objects':['A','A']}]},{'surface_pairs':[{'objects':['A','B'],'max_crossings':-1}]}]:
   with self.assertRaises(ValueError):lab.validate_geometry_spec({'geometry_checks':s})
  lab.validate_geometry_spec({'geometry_checks':{'surface_pairs':[{'objects':['A','B']}]}})
 def test_geometry_regions(self):
  def check(region):
   lab.validate_geometry_spec({'geometry_checks':{'surface_pairs':[{'objects':['A','B'],'region':region}]}})
  check({'min':[-1,-2,-3],'max':[1,2,3]})
  for region in [None,{}, {'min':[0,0,0],'max':[0,1,1]}, {'min':[0,0],'max':[1,1,1]}, {'min':[0,0,0],'max':[1,float('inf'),1]}, {'min':[0,0,0],'max':[1,'2',3]}]:
   with self.assertRaises(ValueError):check(region)

@unittest.skipUnless(os.environ.get('BLENDER_BIN'),'Set BLENDER_BIN for real Blender loop integration')
class LoopBlenderTests(unittest.TestCase):
 def test_region_clips_actual_crossing_segment(self):
  # Two intersecting triangles overlap the ROI in their bounding boxes, but
  # their actual crossing segment lies outside it. Broad-phase-only filtering
  # would incorrectly count this as an in-region crossing.
  with tempfile.TemporaryDirectory() as tmp:
   script=Path(tmp)/'region.py'
   script.write_text("import sys,numpy as np\nsys.path.insert(0,"+repr(str(SCRIPT.parent))+")\nfrom geometry_checks import crossing_count,clip_segment_lengths\n"
    "def mesh(p):\n p=np.array(p,float);t=np.array([[0,1,2]]);return p,t,p[t].min(1),p[t].max(1)\n"
    "a=mesh([[-2,-2,0],[2,-2,0],[0,2,0]])\nb=mesh([[-1,-1,-1],[1,-1,1],[1,1,1]])\n"
    "assert crossing_count(a,b)['confirmed_crossings']==1\n"
    "assert crossing_count(a,b,{'min':[-.1,-.1,-.1],'max':[.1,.1,.1]})['confirmed_crossings']==1\n"
    "outside=crossing_count(a,b,{'min':[-.1,.4,-.1],'max':[.1,.6,.1]})\nassert outside['candidate_pairs']==1 and outside['confirmed_crossings']==0\n"
    "assert crossing_count(a,b,{'min':[3,3,3],'max':[4,4,4]})['confirmed_crossings']==0\n"
    "s=np.array([[[-2,0,0],[2,0,0]],[[0,2,0],[0,3,0]],[[0,0,0],[0,0,0]],[[1,-2,0],[1,2,0]]],float)\n"
    "np.testing.assert_allclose(clip_segment_lengths(s,{'min':[-1,-1,-1],'max':[1,1,1]}),[2,0,0,2])\n")
   subprocess.run([os.environ['BLENDER_BIN'],'-b','--factory-startup','--python-exit-code','1','--python',str(script)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT,timeout=60)
 def test_collision_reject_then_act_verify_select(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);root=Path(os.environ.get('LAB_LOOP_OUTPUT',t.name)).resolve();root.mkdir(parents=True,exist_ok=True)
  asset=root/'fixture.blend';fixture=root/'fixture.py'
  fixture.write_text("import bpy\nbpy.ops.wm.read_factory_settings(use_empty=True)\nbpy.ops.mesh.primitive_cube_add(size=1);bpy.context.object.name='Body'\nbpy.ops.mesh.primitive_cube_add(size=1,location=(.6,.2,.1));bpy.context.object.name='Garment'\nbpy.ops.wm.save_as_mainfile(filepath="+repr(str(asset))+")\n")
  subprocess.run([os.environ['BLENDER_BIN'],'-b','--python-exit-code','1','--python',str(fixture)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT,timeout=60)
  case=root/'case.json';session=root/'lab';lab.write(case,{'goal':'Synthetic crossing loop test','assets':[{'path':str(asset)}],'workflow':['observe','diagnose','edit','inspect','review'],'required_checks':['fixture_translation'],'protected':{'Body':['geometry','transform']},'geometry_checks':{'surface_pairs':[{'objects':['Body','Garment'],'max_crossings':0}]}})
  first=lab.initialize(case,session,os.environ['BLENDER_BIN'],120);self.assertEqual(first['status'],'produced')
  self.assertEqual(lab.read(session/'revisions/r0000/checks.json')['static_surface_crossings'],'fail')
  review=root/'review.json';data={'revision':'r0000','scene_sha256':first['files']['scene.blend'],'reviewer':'fixture automation','decision':'accept','findings':['Try to bypass collision gate'],'checks':{'fixture_translation':{'status':'pass','evidence':['front.png']}}};lab.write(review,data)
  with self.assertRaisesRegex(ValueError,'checks failed'):lab.review(session,'r0000',review)
  packet=root/'observe.json';lab.write(packet,lab.observe(session));op=root/'fix.py';op.write_text("bpy.data.objects['Garment'].location.x=2.0\n")
  decision=root/'decision.json';lab.write(decision,{'observation':str(packet),'observation_sha256':lab.digest(packet),'operation':str(op),'operation_sha256':lab.digest(op),'diagnosis':'Synthetic cubes overlap','edit_scope':'Garment translation only','expected_improvement':'Disjoint surfaces','stop_condition':'Zero configured crossings; fixed Body','viewed_images':[str(session/'revisions/r0000/front.png')]})
  second=lab.act(session,decision,120);self.assertEqual(second['status'],'produced');self.assertEqual(lab.read(session/'revisions/r0001/checks.json')['static_surface_crossings'],'pass');self.assertEqual(lab.read(session/'session.json')['selected'],'r0000')
  data.update(revision='r0001',scene_sha256=second['files']['scene.blend'],findings=['Fixture state transition only, not real character or independent visual acceptance']);lab.write(review,data)
  self.assertEqual(lab.review(session,'r0001',review)['selected'],'r0001')

if __name__=='__main__':unittest.main()
