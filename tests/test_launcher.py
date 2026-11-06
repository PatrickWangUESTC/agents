"""Offline launcher contract tests; these do not test model quality or discovery."""
import argparse
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/agents.py"
spec = importlib.util.spec_from_file_location("launcher", SCRIPT)
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)

FAKE = '''#!/usr/bin/env python3
import json, pathlib, sys, time
args = sys.argv[1:]
workspace = pathlib.Path(args[args.index('-C') + 1])
output = pathlib.Path(args[args.index('--output-last-message') + 1])
prompt = sys.stdin.read()
if prompt == 'timeout':
    time.sleep(30)
if prompt == 'fail':
    print('intentional failure', file=sys.stderr)
    sys.exit(9)
if prompt == 'no-final':
    sys.exit(0)
# Both processes must start before either finishes, proving jobs=2 runs concurrently.
if prompt.startswith('parallel:'):
    barrier = pathlib.Path(prompt.split(':', 1)[1])
    barrier.mkdir(exist_ok=True)
    (barrier / workspace.parent.name).touch()
    end = time.monotonic() + 5
    while len(list(barrier.iterdir())) < 2:
        if time.monotonic() > end:
            sys.exit(8)
        time.sleep(0.02)
(workspace / 'artifacts/result.txt').write_text(prompt)
output.write_text('fake final response')
print(json.dumps({'type': 'test-only'}))
'''


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fake = self.root / "fake codex"
        self.fake.write_text(FAKE)
        self.fake.chmod(0o755)
        self.args = argparse.Namespace(execute=True, codex_bin=str(self.fake),
                                       model=None, timeout=10, jobs=2)

    def task(self, task_id="sample", prompt="hello", input_dir=None):
        return {"id": task_id, "prompt": prompt, "input": input_dir}

    def test_copy_preserves_inputs_and_refuses_overwrite(self):
        source = self.root / "source"
        source.mkdir()
        (source / "asset.txt").write_text("original")
        destination = self.root / "new workspace"
        launcher.prepare(destination, source)
        (destination / "inputs/asset.txt").write_text("changed")
        self.assertEqual((source / "asset.txt").read_text(), "original")
        self.assertTrue((destination / ".git").is_dir())
        with self.assertRaises(ValueError):
            launcher.prepare(destination)
        self.assertEqual((destination / "inputs/asset.txt").read_text(), "changed")

    def test_rejects_symlink_and_recursive_input_copy(self):
        source = self.root / "source"
        source.mkdir()
        with self.assertRaises(ValueError):
            launcher.prepare(source / "nested", source)
        (source / "escape").symlink_to(self.root)
        with self.assertRaises(ValueError):
            launcher.prepare(self.root / "new", source)
        self.assertFalse((self.root / "new").exists())
        with self.assertRaises(ValueError):
            launcher.prepare(launcher.TEMPLATE / "recursive-copy")

    def test_manifest_validation_and_relative_input(self):
        manifest = self.root / "tasks.json"
        source = self.root / "source"
        source.mkdir()
        manifest.write_text(json.dumps([{"id": "one", "prompt": "hello", "input": "source"}]))
        self.assertEqual(launcher.load_tasks(manifest)[0]["input"], source.resolve())
        for tasks in ([{"id": "../escape", "prompt": "x"}],
                      [{"id": "a", "prompt": "x"}] * 2,
                      [{"id": "a", "prompt": " "}],
                      [{"id": "a", "prompt": "x", "typo": "oops"}], []):
            with self.subTest(tasks=tasks):
                manifest.write_text(json.dumps(tasks))
                with self.assertRaises(ValueError):
                    launcher.load_tasks(manifest)

    def test_prepare_without_execution(self):
        self.args.execute = False
        self.args.codex_bin = "definitely-not-installed"
        destination = self.root / "dry"
        results = launcher.launch([self.task()], destination, self.args)
        self.assertEqual(results[0]["status"], "prepared")
        self.assertFalse((destination / "sample/result/events.jsonl").exists())
        self.assertTrue((destination / "summary.json").is_file())

    def test_prompt_is_stdin_data_and_output_is_recorded(self):
        prompt = 'quotes " and $(touch SHOULD_NOT_EXIST)\n第二行 `echo x`'
        destination = self.root / "run with spaces"
        results = launcher.launch([self.task(prompt=prompt)], destination, self.args)
        self.assertEqual(results[0]["status"], "process_completed")
        self.assertEqual(results[0]["acceptance"], "unverified")
        self.assertEqual((destination / "sample/workspace/artifacts/result.txt").read_text(), prompt)
        self.assertFalse((destination / "sample/workspace/SHOULD_NOT_EXIST").exists())
        self.assertTrue((destination / "sample/result/events.jsonl").read_text())

    def test_concurrent_tasks_have_independent_workspaces(self):
        prompt = "parallel:" + str(self.root / "barrier")
        tasks = [self.task("one", prompt), self.task("two", prompt)]
        results = launcher.launch(tasks, self.root / "batch", self.args)
        self.assertEqual([x["status"] for x in results], ["process_completed"] * 2)
        self.assertNotEqual(results[0]["workspace"], results[1]["workspace"])
        for result in results:
            self.assertTrue((Path(result["workspace"]) / "artifacts/result.txt").is_file())

    def test_failure_does_not_hide_success(self):
        results = launcher.launch([self.task("bad", "fail"), self.task("good")],
                                  self.root / "mixed", self.args)
        self.assertEqual([r["status"] for r in results], ["failed", "process_completed"])
        self.assertEqual(results[0]["returncode"], 9)
        self.assertIn("intentional failure", (self.root / "mixed/bad/result/stderr.log").read_text())

    def test_zero_exit_without_final_is_failure(self):
        result = launcher.launch([self.task(prompt="no-final")], self.root / "no-final", self.args)
        self.assertEqual(result[0]["status"], "failed")

    def test_timeout_is_reported(self):
        self.args.timeout = 0.2
        results = launcher.launch([self.task(prompt="timeout")], self.root / "timeout", self.args)
        self.assertEqual(results[0]["status"], "timed_out")
        saved = json.loads((self.root / "timeout/sample/result/status.json").read_text())
        self.assertEqual(saved["status"], "timed_out")

    def test_missing_executable_does_not_create_run(self):
        self.args.codex_bin = "definitely-not-installed"
        destination = self.root / "missing"
        with self.assertRaises(ValueError):
            launcher.launch([self.task()], destination, self.args)
        self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
