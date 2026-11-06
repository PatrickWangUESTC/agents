---
name: character-canvas
description: Plan and coordinate a reference-to-character pipeline with named parts, saved node outputs, local revision branches, and explicit generation, assembly, rigging, and delivery evidence.
---

Use this for a multi-stage character task. For a narrow existing-asset edit,
use character-local-edit directly. This is an agent-directed pipeline; the JSON
graph is an artifact ledger, not a replacement for choosing and executing tools.

Establish a brief: reference image or existing asset paths, intended usage,
parts, units/up axis/front axis, polygon budget, texture expectations, rig and
export requirements. Ask only where a missing answer changes the result. Keep
assumptions explicit. Put the brief and graph under artifacts/character/.

Use scripts/pipeline.py to create the graph and record node artifacts and checks.
Run `python3 <skill-dir>/scripts/pipeline.py --help` for commands. The bundled
workflow/fixtures/character/brief.json in the library is a brief example, not a
real character or reference. Supply real input paths in an actual task.

Each part gets a reference-preparation and generation node; assembly consumes all
parts. Rig, export, and engine validation follow assembly. Local revision forks
the ledger, reuses unaffected evidence, and invalidates the changed branch and
its descendants. Never overwrite an accepted source asset in place.

Discover actual backend tools before claiming execution. Record provider task IDs
and resume existing asynchronous jobs; do not resubmit on an uncertain timeout.
If generation/rigging/engine tools are absent, record blocked and the exact
handoff required. A text plan, mock file, or procedural fixture is not a generated
character. No adapter to Tripo Studio is implied by this skill.

For execution, use character-assembly, character-local-edit, and character-delivery
at the corresponding nodes. Optional custom roles are character_planner,
character_builder, and character_critic when the user requests delegation.
Part-generation tasks may run independently; writes to a shared Blender scene
must be sequential. The coordinator alone writes the shared ledger; workers
return artifact paths and evidence rather than racing to update it. Reuse
existing user authorization. In default auto mode,
proceed through authorized steps; use review checkpoints when the user asks for
control mode, or a consequential decision genuinely needs their input.

Node output means produced, not accepted. Acceptance requires current artifact
hashes and evidence with named checks. Keep unknown/not_run separate from pass.
The ledger validates evidence format and freshness, not truth or visual quality.
