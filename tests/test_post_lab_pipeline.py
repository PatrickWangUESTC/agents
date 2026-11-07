"""Post-Lab gates with synthetic files, not character/model execution."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

pipeline = module('post_lab_pipeline', 'workspace/.agents/skills/character-canvas/scripts/pipeline.py')
preflight = module('rig_preflight', 'workspace/.agents/skills/character-delivery/scripts/rig_preflight.py')


class PostLabTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.session = self.root / 'lab'
        self.rev = self.session / 'revisions/r0001'
        self.rev.mkdir(parents=True)
        self.case = self.session / 'case.json'
        self.case.write_text('{"goal":"fixture"}')
        files = {}
        for name in ['scene.blend', 'inventory.json', 'checks.json', 'readback.json', 'views.json']:
            p = self.rev / name
            p.write_text('fixture only')
            files[name] = pipeline.snapshot(p)['sha256']
        (self.rev / 'receipt.json').write_text(json.dumps({
            'revision': 'r0001', 'status': 'produced', 'acceptance': 'accepted', 'files': files}))
        (self.session / 'session.json').write_text(json.dumps({
            'selected': 'r0001', 'case_sha256': pipeline.snapshot(self.case)['sha256']}))
        self.brief = self.root / 'brief.json'
        self.brief.write_text(json.dumps({'parts': ['body', 'clothing', 'shoes'], 'constraints': {'rig_required': True},
                                         'delivery': {'engine': {'enabled': False}}}))
        self.ledger = self.root / 'ledger.json'

    def init(self, **changes):
        data = json.loads(self.brief.read_text())
        data.update(changes)
        self.brief.write_text(json.dumps(data))
        self.graph = pipeline.continue_from_lab(self.brief, self.ledger, self.session)
        return self.graph

    def evidence(self, node, verdict='pass', names=None):
        artifact = self.root / (node + '.asset')
        artifact.write_text('fixture artifact, not geometry')
        snap = pipeline.snapshot(artifact)
        names = self.graph['nodes'][node]['required_checks'] if names is None else names
        path = self.root / (node + '.json')
        path.write_text(json.dumps({'scope': 'Synthetic gate test only',
            'artifact_sha256': {snap['path']: snap['sha256']},
            'checks': [{'name': n, 'status': verdict, 'evidence': [str(artifact)]} for n in names]}))
        pipeline.record(self.graph, node, [artifact], path)

    def test_task_accepted_does_not_accept_asset_and_engine_deferred(self):
        g = self.init()
        self.assertEqual(pipeline.states(g)['lab_checkpoint'], 'accepted')
        self.assertEqual(pipeline.states(g)['assembly_review'], 'pending')
        self.assertNotIn('engine', g['nodes'])
        self.assertEqual(g['deferred'][0]['status'], 'not_run')
        with self.assertRaisesRegex(ValueError, 'Dependency'):
            self.evidence('rig')

    def test_intersection_failure_blocks_rig(self):
        self.init()
        self.evidence('assembly_review', 'fail')
        self.assertEqual(pipeline.states(self.graph)['assembly_review'], 'produced')
        with self.assertRaisesRegex(ValueError, 'Dependency'):
            self.evidence('rig')

    def test_completion_or_incomplete_check_cannot_bypass_quality_gate(self):
        self.init()
        for names in [['audit_completed'], ['part_inventory'], ['part_inventory', 'part_inventory']]:
            with self.assertRaises(ValueError):
                self.evidence('assembly_review', names=names)

    def test_successful_fixture_path_and_mutation_invalidates_downstream(self):
        self.init(delivery={'engine': {'enabled': True, 'target': 'test engine'}})
        for node in list(self.graph['nodes'])[1:]:
            self.evidence(node)
        self.assertEqual(pipeline.states(self.graph)['engine'], 'accepted')
        (self.rev / 'scene.blend').write_text('changed')
        self.assertEqual(set(pipeline.states(self.graph).values()), {'stale'})

    def test_receipt_file_or_case_tampering_rejected(self):
        (self.rev / 'checks.json').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'checkpoint changed'):
            self.init()
        self.case.write_text('changed case')
        with self.assertRaisesRegex(ValueError, 'case has changed'):
            self.init()

    def test_fork_keeps_required_gates(self):
        self.init()
        self.evidence('assembly_review')
        pipeline.write(self.ledger, self.graph)
        revised = pipeline.fork(self.graph, 'assembly_review', self.ledger)
        for node in revised['nodes']:
            self.assertEqual(revised['nodes'][node]['required_checks'],
                             self.graph['nodes'][node]['required_checks'])
        self.assertEqual(revised['nodes']['rig']['skills'], ['character-rigging'])
        self.assertEqual(pipeline.states(revised)['assembly_review'], 'pending')
        self.assertEqual(pipeline.states(revised)['lab_checkpoint'], 'accepted')

    def test_optional_upgrade_and_static_delivery(self):
        g = self.init(local_upgrade={'enabled': True, 'part': 'head', 'reason': 'requested detail'},
                      constraints={'rig_required': False})
        self.assertEqual(g['nodes']['assembly_review']['deps'], ['local_upgrade'])
        self.assertNotIn('rig', g['nodes'])
        self.assertNotIn('pose_test', g['nodes'])
        self.assertEqual(g['nodes']['export']['deps'], ['assembly_review'])

    def test_unrequested_facial_branch_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Facial'):
            self.init(delivery={'facial_controls': True})

    def test_rig_never_silently_drops_shoes(self):
        self.assertEqual(preflight.validate_parts({'parts': ['body', 'cloth']}, ['body', 'cloth']),
                         ['body', 'cloth'])
        with self.assertRaisesRegex(ValueError, 'unlisted meshes'):
            preflight.validate_parts({'parts': ['body', 'cloth']}, ['body', 'cloth', 'shoe'])
        with self.assertRaisesRegex(ValueError, 'explicit shoe'):
            preflight.validate_parts({'parts': ['body', 'cloth', 'shoe']}, ['body', 'cloth', 'shoe'])


if __name__ == '__main__':
    unittest.main()
