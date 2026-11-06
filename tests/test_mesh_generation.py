import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('mesh_generation', ROOT /
    'workspace/.agents/skills/mesh-generation/scripts/generate.py')
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)


class Fake:
    name = 'n4d'
    def __init__(self, states=None):
        self.submissions = 0
        self.states = iter(states or [{'status': 'ready', 'model_url': 'https://assets.example/test.glb'}])
    def submit(self, prompt):
        self.submissions += 1
        return 'job-123'
    def poll(self, job):
        assert job == 'job-123'
        return next(self.states)


def downloader(url, path):
    path.write_bytes(b'fixture, not a real GLB')
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'bytes': path.stat().st_size}


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name) / 'job'

    def test_handle_saved_before_poll_and_resume_never_submits(self):
        provider = Fake()
        g.begin(self.out, 'a robot', provider)
        self.assertEqual(json.loads((self.out/'job.json').read_text())['job_id'], 'job-123')
        result = g.resume(self.out, provider, downloader=downloader)
        self.assertEqual(result['status'], 'downloaded')
        g.resume(self.out, provider, downloader=downloader)
        self.assertEqual(provider.submissions, 1)
        self.assertEqual(result['acceptance'], 'unverified')

    def test_uncertain_submit_blocks_repeated_submission(self):
        class Uncertain(Fake):
            def submit(self, prompt):
                raise TimeoutError('request may have reached server')
        provider = Uncertain()
        with self.assertRaises(TimeoutError):
            g.begin(self.out, 'robot', provider)
        self.assertEqual(json.loads((self.out/'job.json').read_text())['status'], 'submission_unknown')
        with self.assertRaises(ValueError):
            g.resume(self.out, provider)
        with self.assertRaises(FileExistsError):
            g.begin(self.out, 'robot', provider)

    def test_wait_timeout_can_resume_same_job(self):
        provider = Fake([{'status': 'running'}, {'status': 'ready', 'model_url': 'https://assets.example/test.glb'}])
        g.begin(self.out, 'robot', provider)
        self.assertEqual(g.resume(self.out, provider, timeout=0, downloader=downloader)['status'], 'waiting_timeout')
        self.assertEqual(g.resume(self.out, provider, downloader=downloader)['status'], 'downloaded')
        self.assertEqual(provider.submissions, 1)

    def test_download_failure_can_resume_without_new_generation(self):
        provider = Fake([{'status': 'ready', 'model_url': 'https://assets.example/test.glb'}] * 2)
        g.begin(self.out, 'robot', provider)
        def broken(url, path): raise OSError('storage offline')
        with self.assertRaises(OSError): g.resume(self.out, provider, downloader=broken)
        self.assertEqual(json.loads((self.out/'job.json').read_text())['status'], 'download_error')
        self.assertEqual(g.resume(self.out, provider, downloader=downloader)['status'], 'downloaded')
        self.assertEqual(provider.submissions, 1)

    def test_source_mutation_is_detected(self):
        provider = Fake()
        g.begin(self.out, 'robot', provider)
        result = g.resume(self.out, provider, downloader=downloader)
        Path(result['artifact']['path']).write_text('changed')
        with self.assertRaises(ValueError): g.resume(self.out, provider)

    def test_provider_status_unknown_does_not_become_success(self):
        provider = g.N4D('test-only')
        provider.request = lambda *args: {'codeStatus': 25}
        with self.assertRaises(RuntimeError): provider.poll('job')
        provider.request = lambda *args: {'codeStatus': 0}
        with self.assertRaises(RuntimeError): provider.poll('job')

    def test_image_submission_uploads_file_and_limits_candidate_count(self):
        image = Path(self.tmp.name) / 'input.png'
        image.write_bytes(b'fake-png-bytes')
        provider = g.N4D('test-only')
        captured = []
        def request(*args):
            captured.append(args)
            return {'uuids': ['image-job'], 'pointsDeducted': 20}
        provider.request = request
        self.assertEqual(provider.submit_image(image), 'image-job')
        endpoint, body, content_type = captured[0]
        self.assertEqual(endpoint, 'generateModelWithImage')
        self.assertTrue(content_type.startswith('multipart/form-data; boundary='))
        self.assertIn(b'name="image"; filename="reference.png"', body)
        self.assertIn(b'fake-png-bytes', body)
        self.assertIn(b'name="modelCount"\r\n\r\n1\r\n', body)
        self.assertIn(b'name="disablePbr"\r\n\r\n1\r\n', body)
        self.assertEqual(provider.last_receipt['pointsDeducted'], 20)

    def test_matting_resume_does_not_upload_again(self):
        image = Path(self.tmp.name) / 'input.png'
        image.write_bytes(b'fixture-image')
        class ImageProvider(Fake):
            uploads = 0
            result = {}
            def matting(self, image): self.uploads += 1; return 33
            def matted(self, request): return self.result
        provider = ImageProvider()
        with self.assertRaises(TimeoutError):
            g.prepare_image(self.out, image, provider, timeout=0)
        provider.result = {'fileKeys': ['key'], 'mattedImageUrls': ['https://example/matted.png']}
        with patch.object(g, 'download', downloader):
            state = g.prepare_image(self.out, image, provider)
            self.assertEqual(state['status'], 'matting_ready')
            g.prepare_image(self.out, image, provider)
        self.assertEqual(provider.uploads, 1)
        self.assertTrue((self.out/'matted.png').is_file())

    def test_image_input_change_and_duplicate_submission_rejected(self):
        self.out.mkdir()
        image = self.out/'reference.png'
        image.write_bytes(b'reference')
        (self.out/'matted.png').write_bytes(b'prepared')
        g.save(self.out/'preprocess.json', {'status': 'matting_ready',
            'image_path': str(image), 'image_sha256': hashlib.sha256(image.read_bytes()).hexdigest(),
            'request_id': 33, 'file_keys': ['key']})
        class ImageProvider(Fake):
            def submit_image(self, path):
                self.submissions += 1
                self.last_receipt = {'pointsDeducted': 20}
                return 'image-job'
        provider = ImageProvider()
        g.begin_image(self.out, provider)
        with self.assertRaises(FileExistsError): g.begin_image(self.out, provider)
        self.assertEqual(provider.submissions, 1)
        self.assertEqual(json.loads((self.out/'job.json').read_text())['provider_receipt']['pointsDeducted'], 20)
        image.write_bytes(b'changed')
        with self.assertRaises(ValueError): g.begin_image(self.out, provider)

    def test_failed_matting_keeps_redacted_response_without_reupload(self):
        image = Path(self.tmp.name) / 'input.png'
        image.write_bytes(b'fixture-image')
        provider = g.N4D('test-only-secret')
        calls = []
        def rejected(*args):
            calls.append(args[0])
            return {'message': 'Busy test-only-secret', 'arbitrary_private_field': 'omit'}
        provider.request = rejected
        with self.assertRaises(RuntimeError):
            g.prepare_image(self.out, image, provider)
        state = json.loads((self.out/'preprocess.json').read_text())
        self.assertEqual(state['submission_response'], {'message': 'Busy [REDACTED]'})
        with self.assertRaises(ValueError):
            g.prepare_image(self.out, image, provider)
        self.assertEqual(calls, ['mattingImage'])

    def test_failed_image_submission_keeps_provider_response(self):
        self.out.mkdir()
        image = self.out/'reference.png'
        image.write_bytes(b'reference')
        (self.out/'matted.png').write_bytes(b'prepared')
        g.save(self.out/'preprocess.json', {'status': 'matting_ready',
            'image_path': str(image), 'image_sha256': hashlib.sha256(image.read_bytes()).hexdigest(),
            'request_id': 33})
        provider = g.N4D('test-secret')
        provider.request = lambda *a: {'message': 'Your task is already being processed, please submit again later'}
        with self.assertRaises(RuntimeError): g.begin_image(self.out, provider)
        job = json.loads((self.out/'job.json').read_text())
        self.assertEqual(job['status'], 'submission_unknown')
        self.assertIn('already being processed', job['submission_response']['message'])
        with self.assertRaises(FileExistsError): g.begin_image(self.out, provider)


if __name__ == '__main__': unittest.main()
