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

For humanoid generation from a posed or cropped source that needs normalization,
set reference_preparation.apose_required=true. Existing usable meshes start in the
Lab, and a nonhumanoid asset needs a reference-appropriate pose rather than A-pose.
The graph then requires reference -> apose -> extract/<part> -> generate/<part>.
Use the available image generation tool to make the full front A-pose first and
inspect identity, outfit, complete extremities and pose before extracting parts.
Retain source/reference prompts and explicitly label occluded geometry inference.
Choose semantic parts from the actual reference and editable requirements. Body
(including head/hair), clothing and shoes is one humanoid example, not a required
split; keep accessories or separate hair/head only when useful for this case. A null polygon budget means no decimation.

Each part gets a reference-preparation and generation node; assembly consumes all
parts. Export follows assembly. Rigging requires explicit constraints.rig_required=true;
engine validation requires delivery.engine.enabled=true and a target. New ledgers
do not schedule either by default. Existing ledgers retain their recorded graph. Local revision forks
the ledger, reuses unaffected evidence, and invalidates the changed branch and
its descendants. Never overwrite an accepted source asset in place.

Discover actual backend tools before claiming execution. Use mesh-generation
for the available N4D text/image adapter. Keep native outputs by default; an explicitly requested lowpoly
output is locally decimated, not verified native Smart Mesh. A text-only brief
can serve as the reference node; record that scope instead of inventing an image.
Record provider task IDs
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

For a user-requested continuation after AI 3D Lab, use `scripts/pipeline.py from-lab
BRIEF LEDGER --session LAB_DIR`. It pins the selected scene and verifies its receipt;
only checkpoint integrity is accepted automatically. The new graph requires named
assembly/rig/pose/export/roundtrip checks, optional requested part replacement and
optional enabled engine validation. Read each node's required_checks before recording.
Never replace failed intersection_review with a passing audit-completed check. Follow
repository docs/post-lab-workflow.md and workflow/prompts/post-lab.md when available.
A repaired Lab revision needs a fresh handoff; do not mutate the pinned scene.

Post-Lab nodes now name executable skills: local_upgrade uses character-part-upgrade; rig and pose_test use character-rigging; skeleton FBX export/roundtrip use character-fbx-export, with character-delivery for other formats and engine work. Static exports stay with character-delivery. Read the routed skill and use its actual input contract rather than inferring backend support from eligibility.
