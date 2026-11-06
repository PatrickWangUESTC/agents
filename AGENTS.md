# Repository maintenance

This repository distributes a Codex workspace template and a small launcher.
Keep runtime instructions in `workspace/AGENTS.md`, reusable capabilities in
`workspace/.agents/skills/`, and custom roles in `workspace/.codex/agents/`.
`workflow/` contains task inputs and recipes, not an automatically loaded engine.

Use Python 3.11+ standard library for the launcher. Verify changes with
`python3 scripts/agents.py validate` and `python3 -m unittest discover -s tests -v`.
Keep generated runs, chat records, credentials, and private inputs out of Git.
Do not turn a successful launcher test into a claim of successful model execution.
