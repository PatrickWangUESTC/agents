from pathlib import Path
import re
import tempfile
import unittest

from test_launcher import launcher


class CharacterEntryTests(unittest.TestCase):
    def test_prepared_workspace_routes_to_bundled_assemble(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = launcher.prepare(Path(directory) / "character")
            catalog = launcher.validate(workspace)
            self.assertIn("agent_anime", catalog["roles"])
            self.assertIn("assemble", catalog["skills"])
            entry = workspace / ".agents/skills/agentic-character/SKILL.md"
            link = re.search(r"\[assemble\]\(([^)]+)\)", entry.read_text())
            self.assertIsNotNone(link)
            skill = entry.parent / link.group(1)
            self.assertIn("name: assemble\n", skill.read_text())
            self.assertTrue((skill.parent / "scripts/assemble.py").is_file())
