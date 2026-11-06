"""Ledger dependency/evidence behavior; no provider or Blender required."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "workspace/.agents/skills/character-canvas/scripts/pipeline.py"
spec = importlib.util.spec_from_file_location("pipeline", SCRIPT)
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)


class CharacterPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.brief = self.root / "brief.json"
        self.brief.write_text(json.dumps({"parts": ["body", "head"]}))
        self.path = self.root / "ledger.json"
        self.graph = pipeline.initialize(self.brief, self.path)

    def accept(self, key, verdict="pass"):
        label = key.replace("/", "-")
        artifact = self.root / (label + ".asset")
        artifact.write_text("fixture:" + key)
        observation = self.root / (label + ".check.txt")
        observation.write_text("Test-only observation; no geometry claims")
        evidence = self.root / (label + ".json")
        snap = pipeline.snapshot(artifact)
        evidence.write_text(json.dumps({"scope": "Ledger test only",
            "artifact_sha256": {snap["path"]: snap["sha256"]},
            "checks": [{"name": "fixture", "status": verdict, "evidence": [str(observation)]}]}))
        pipeline.record(self.graph, key, [artifact], evidence)
        return artifact, evidence, observation

    def accept_all(self):
        for key in self.graph["nodes"]:
            self.accept(key)

    def test_cannot_record_before_dependencies(self):
        with self.assertRaises(ValueError):
            self.accept("assemble")

    def test_unknown_check_is_produced_and_blocks_descendants(self):
        self.accept("reference", "unknown")
        self.assertEqual(pipeline.states(self.graph)["reference"], "produced")
        with self.assertRaises(ValueError):
            self.accept("extract/head")

    def test_empty_or_wrong_bound_evidence_is_rejected(self):
        artifact, evidence, observation = self.accept("reference", "unknown")
        for change in ({"checks": []}, {"artifact_sha256": {}},
                       {"checks": [{"name": "x", "status": "PASS", "evidence": [str(observation)]}]}):
            data = json.loads(evidence.read_text())
            data.update(change)
            evidence.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                pipeline.record(self.graph, "reference", [artifact], evidence)

    def test_modified_artifact_invalidates_all_dependents(self):
        self.accept_all()
        node = self.graph["nodes"]["generate/head"]
        Path(node["artifacts"][0]["path"]).write_text("changed")
        states = pipeline.states(self.graph)
        for key in ("generate/head", "assemble", "rig", "export", "engine"):
            self.assertEqual(states[key], "stale")
        self.assertEqual(states["generate/body"], "accepted")

    def test_modified_evidence_observation_invalidates_acceptance(self):
        artifact, evidence, observation = self.accept("reference")
        observation.write_text("changed")
        self.assertEqual(pipeline.states(self.graph)["reference"], "stale")

    def test_fork_preserves_base_and_unaffected_parts(self):
        self.accept_all()
        pipeline.write(self.path, self.graph)
        forked = pipeline.fork(self.graph, "generate/head", self.path)
        self.assertEqual(pipeline.states(self.graph)["engine"], "accepted")
        states = pipeline.states(forked)
        self.assertEqual(states["generate/body"], "accepted")
        self.assertEqual(states["extract/head"], "accepted")
        for key in ("generate/head", "assemble", "rig", "export", "engine"):
            self.assertEqual(states[key], "pending")

    def test_cannot_overwrite_accepted_node_or_ledger(self):
        self.accept("reference")
        with self.assertRaises(ValueError):
            self.accept("reference")
        with self.assertRaises(FileExistsError):
            pipeline.initialize(self.brief, self.path)


if __name__ == "__main__":
    unittest.main()
