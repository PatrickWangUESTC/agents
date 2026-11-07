"""Input integrity and protected-geometry contracts; Blender verified separately."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "workspace/.agents/skills/character-assembly/scripts/lab.py"
spec = importlib.util.spec_from_file_location("local_lab", SCRIPT)
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)


class LocalLabTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for name in ['body.glb', 'clothing.glb', 'reference.png']:
            (self.root / name).write_bytes(b'input-integrity-test-only')
        self.config = {'schema_version': 1, 'instruction': 'Assemble supplied parts',
                       'reference': 'reference.png', 'parts': [
                           {'name': 'body', 'source': 'body.glb', 'protected_geometry': True},
                           {'name': 'clothing', 'source': 'clothing.glb'}]}
        self.path = self.root / 'config.json'

    def run_config(self, config=None):
        self.path.write_text(json.dumps(config or self.config))
        return lab.prepare(self.path)

    def test_relative_paths_and_input_hash_binding(self):
        result = self.run_config()
        self.assertEqual(result['parts'][0]['source'], str((self.root / 'body.glb').resolve()))
        (self.root / 'body.glb').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Changed input'):
            self.run_config(result)

    def test_protected_geometry_rejects_local_deformation(self):
        self.config['parts'][0]['fit_profile'] = [[0, 1.1, 1, 0, 0]]
        with self.assertRaisesRegex(ValueError, 'protected geometry'):
            self.run_config()

    def test_local_offset_requires_unprotected_part_and_positive_radius(self):
        edit = {'center': [0, 0, 0], 'radius': [1, 1, 1], 'delta': [0, .02, 0]}
        cfg = copy.deepcopy(self.config)
        cfg['parts'][0]['local_offsets'] = [edit]
        with self.assertRaisesRegex(ValueError, 'protected geometry'):
            self.run_config(cfg)
        cfg = copy.deepcopy(self.config)
        edit['radius'][0] = 0
        cfg['parts'][1]['local_offsets'] = [edit]
        with self.assertRaises(ValueError):
            self.run_config(cfg)

    def test_invalid_transforms_and_profiles(self):
        for change in [{'scale': [0, 1, 1]}, {'translation': [0, float('nan'), 0]},
                       {'rotation_degrees': [0, 0]}, {'fit_profile': [[1, 1, 1, 0, 0], [0, 1, 1, 0, 0]]}]:
            with self.subTest(change=change):
                cfg = copy.deepcopy(self.config)
                cfg['parts'][1].update(change)
                with self.assertRaises(ValueError):
                    self.run_config(cfg)

    def test_duplicate_part_names_rejected(self):
        self.config['parts'][1]['name'] = 'body'
        with self.assertRaisesRegex(ValueError, 'unique'):
            self.run_config()

    def test_clearance_cannot_edit_protected_body_or_use_missing_target(self):
        for index, target in [(0, 'clothing'), (1, 'absent'), (1, 'clothing')]:
            cfg = copy.deepcopy(self.config)
            cfg['parts'][index]['surface_clearance'] = {'target': target, 'margin': .01, 'max_displacement': .1}
            with self.assertRaisesRegex(ValueError, 'different supplied target'):
                self.run_config(cfg)


if __name__ == '__main__':
    unittest.main()
