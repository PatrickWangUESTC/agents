"""Real Blender smoke test, opt in with BLENDER_BIN; synthetic assets only."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT/'workspace/.agents/skills'
BLENDER = os.environ.get('BLENDER_BIN')


def snap(path):
    return {'path':str(path), 'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


@unittest.skipUnless(BLENDER, 'Set BLENDER_BIN for real Blender integration')
class DeliverySkillsBlenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        supplied=os.environ.get('DELIVERY_TEST_OUTPUT')
        if supplied:
            cls.root=Path(supplied).resolve();cls.root.mkdir(parents=True,exist_ok=False)
        else:
            cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name)
        cls.run_script(ROOT/'tests/blender/create_delivery_fixture.py',[cls.root], 'fixture')
        cls.run_script(SKILLS/'character-part-upgrade/scripts/upgrade.py',[cls.root/'upgrade.json',cls.root/'upgrade'], 'upgrade')
        config={'source':snap(cls.root/'upgrade/candidate.blend'),
                'bones':json.loads((cls.root/'bones.json').read_text()),
                'reference_skeleton':json.loads((cls.root/'reference.json').read_text()),
                'bindings':{'Body':{'mode':'weights',**snap(cls.root/'body-weights.json')},
                 'Clothing':{'mode':'automatic'}, 'HeadNew':{'mode':'rigid','bone':'head'},
                 'ShoeLeft':{'mode':'rigid','bone':'foot_l'},'ShoeRight':{'mode':'rigid','bone':'foot_r'}}}
        cls.config=config;(cls.root/'rig.json').write_text(json.dumps(config))
        cls.run_script(SKILLS/'character-rigging/scripts/bind.py',[cls.root/'rig.json',cls.root/'rig'], 'rig')
        cls.export={'source':snap(cls.root/'rig/rigged.blend'),'parts':list(config['bindings']),
                    'diagnostic_poses':[{'bone':bone,'axis':axis,'degrees':degrees}
                      for bone,axis,degrees in [('root','Y',15),('head','X',20),('foot_l','X',25),('foot_r','X',-20)]]}
        (cls.root/'export.json').write_text(json.dumps(cls.export))
        cls.run_script(SKILLS/'character-fbx-export/scripts/export_fbx.py',[cls.root/'export.json',cls.root/'fbx'], 'export')

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls,'temp'):cls.temp.cleanup()

    @classmethod
    def run_script(cls,script,args,label,success=True):
        result=subprocess.run([BLENDER,'-b','--python-exit-code','1','--python',str(script),'--',*map(str,args)],capture_output=True,text=True,timeout=180)
        (cls.root/(label+'.log')).write_text(result.stdout+result.stderr)
        if success and result.returncode:
            raise AssertionError((result.stdout+result.stderr)[-5000:])
        if not success and result.returncode==0:
            raise AssertionError('Expected rejection, got success')
        return result

    def test_replacement_preserves_non_target_and_source(self):
        report=json.loads((self.root/'upgrade/upgrade-report.json').read_text())
        self.assertEqual(report['protected_before'],report['protected_after'])
        self.assertEqual(report['removed'],['HeadOld']);self.assertEqual(report['added'],['HeadNew'])
        self.assertEqual(snap(Path(report['source']['path'])),report['source'])
        self.assertEqual(report['checks']['visual_review'],'not_run')

    def test_all_parts_bound_and_fbx_pose_roundtrip(self):
        report=json.loads((self.root/'rig/rig-report.json').read_text())
        self.assertEqual(set(report['bindings']),set(self.config['bindings']))
        result=json.loads((self.root/'fbx/roundtrip.json').read_text())
        self.assertEqual(result['status'],'pass')
        self.assertEqual(len(result['comparisons']),5)
        self.assertEqual(len(result['inventory']['bones']),4)

    def test_fused_or_missing_head_rejected(self):
        c=json.loads((self.root/'upgrade.json').read_text());c['targets']=['BodyHeadFusedRegion']
        p=self.root/'bad-upgrade.json';p.write_text(json.dumps(c))
        r=self.run_script(SKILLS/'character-part-upgrade/scripts/upgrade.py',[p,self.root/'bad-upgrade'],'bad-upgrade',False)
        self.assertIn('fused regions',r.stdout+r.stderr)

    def test_unlisted_shoe_rejected_by_binding(self):
        c=json.loads(json.dumps(self.config));del c['bindings']['ShoeRight']
        p=self.root/'bad-rig.json';p.write_text(json.dumps(c))
        r=self.run_script(SKILLS/'character-rigging/scripts/bind.py',[p,self.root/'bad-rig'],'bad-rig',False)
        self.assertIn('Complete mesh inventory',r.stdout+r.stderr)

    def test_fbx_export_does_not_silently_reset_existing_pose(self):
        script=self.root/'make-posed.py'
        script.write_text("import bpy\n"
            +"bpy.ops.wm.open_mainfile(filepath="+repr(str(self.root/'rig/rigged.blend'))+")\n"
            +"rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')\n"
            +"rig.pose.bones['head'].rotation_mode='XYZ'\nrig.pose.bones['head'].rotation_euler.x=0.25\n"
            +"bpy.ops.wm.save_as_mainfile(filepath="+repr(str(self.root/'posed.blend'))+")\n")
        self.run_script(script,[], 'make-posed')
        c=json.loads(json.dumps(self.export));c['source']=snap(self.root/'posed.blend')
        p=self.root/'posed-export.json';p.write_text(json.dumps(c))
        r=self.run_script(SKILLS/'character-fbx-export/scripts/export_fbx.py',[p,self.root/'posed-export'],'posed-export',False)
        self.assertIn('Input is not at rest',r.stdout+r.stderr)

    def test_fbx_export_rejects_missing_shoe(self):
        c=json.loads(json.dumps(self.export));c['parts'].remove('ShoeRight')
        p=self.root/'bad-export.json';p.write_text(json.dumps(c))
        r=self.run_script(SKILLS/'character-fbx-export/scripts/export_fbx.py',[p,self.root/'bad-export'],'bad-export',False)
        self.assertIn('every character mesh',r.stdout+r.stderr)


if __name__=='__main__':unittest.main()
