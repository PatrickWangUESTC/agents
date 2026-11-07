"""Review state integrity; real Blender execution is tested separately."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'workspace/.agents/skills/three-d-ai-lab/scripts/lab.py'
spec = importlib.util.spec_from_file_location('three_d_ai_lab', SCRIPT)
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)


class LabReviewTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        lab.write(self.root / 'case.json', {'required_checks': ['placement']})
        lab.write(self.root / 'session.json', {'selected': 'r0000',
                  'case_sha256': lab.digest(self.root / 'case.json')})
        self.out = self.root / 'revisions/r0001'
        self.out.mkdir(parents=True)
        (self.out / 'scene.blend').write_bytes(b'fixture, not Blender content')
        (self.out / 'front.png').write_bytes(b'fixture, not image content')
        lab.write(self.out / 'checks.json', {'Body:geometry': 'pass'})
        self.receipt = {'status': 'produced', 'files': {p.name: lab.digest(p) for p in self.out.iterdir()}}
        self.save_receipt()
        self.report = {'revision': 'r0001', 'scene_sha256': lab.digest(self.out / 'scene.blend'),
                       'reviewer': 'test', 'decision': 'accept', 'findings': ['fixture'],
                       'checks': {'placement': {'status': 'pass', 'evidence': ['front.png']}}}

    def save_receipt(self):
        lab.write(self.out / 'receipt.json', self.receipt)

    def review(self):
        lab.write(self.root / 'review-input.json', self.report)
        return lab.review(self.root, 'r0001', self.root / 'review-input.json')

    def test_accept_updates_selected_but_cannot_overwrite_review(self):
        self.assertEqual(self.review()['selected'], 'r0001')
        with self.assertRaisesRegex(ValueError, 'Review exists'):
            self.review()

    def test_reject_retains_selected_checkpoint(self):
        self.report['decision'] = 'reject'
        self.assertEqual(self.review()['selected'], 'r0000')

    def test_changed_preview_cannot_be_accepted(self):
        (self.out / 'front.png').write_bytes(b'other candidate')
        with self.assertRaisesRegex(ValueError, 'Stale'):
            self.review()

    def test_failed_protection_cannot_be_accepted(self):
        lab.write(self.out / 'checks.json', {'Body:geometry': 'fail'})
        self.receipt['files']['checks.json'] = lab.digest(self.out / 'checks.json')
        self.save_receipt()
        with self.assertRaisesRegex(ValueError, 'checks failed'):
            self.review()

    def test_missing_or_foreign_evidence_cannot_be_accepted(self):
        for check in [{'status': 'not_run', 'evidence': ['front.png']},
                      {'status': 'pass', 'evidence': ['../r0000/front.png']},
                      {'status': 'pass', 'evidence': []}]:
            self.report['checks']['placement'] = check
            with self.assertRaises(ValueError):
                self.review()

    def test_case_changes_require_new_branch(self):
        lab.write(self.root / 'case.json', {'required_checks': []})
        with self.assertRaisesRegex(ValueError, 'Case changed'):
            self.review()

    def test_lock_excludes_second_writer(self):
        with lab.lock(self.root):
            with self.assertRaises(FileExistsError):
                with lab.lock(self.root):
                    self.fail('second writer acquired the lock')
        self.assertFalse((self.root / '.lock').exists())

    def test_fixed_camera_change_invalidates_session(self):
        lab.write(self.root / 'views.json', {'span': 2})
        state = lab.read(self.root / 'session.json')
        state['views_sha256'] = lab.digest(self.root / 'views.json')
        lab.write(self.root / 'session.json', state)
        lab.write(self.root / 'views.json', {'span': 3})
        with self.assertRaisesRegex(ValueError, 'Fixed views changed'):
            self.review()


if __name__ == '__main__':
    unittest.main()
