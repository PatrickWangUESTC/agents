---
name: character-assembly
description: Assemble separately generated body, clothing, shoes, and accessories into an editable character while preserving source assets and named part identities.
---

Inspect actual mesh parts, reference views, units, coordinate frames, materials,
UVs, morphs and rigs. Save a source inventory and checkpoint before editing.
Use explicit part names and transforms; infer attachments from the brief and
available geometry. A single reference does not provide unseen ground truth.

Import into a new scene or scoped collection. Preserve source files and native
materials. Align scale, orientation and attachment points. Save an editable
.blend, the reproducible script, and fresh front/side/back renders of that same
revision. Record interpenetrations, gaps and ambiguous attachment choices.

Check silhouette, part placement, materials and intended mesh budget. Use spatial
contact/intersection checks where the brief requires them; counts and a render
alone cannot establish clearance. Do not weld or remesh all components merely
to obtain one connected mesh. Record partial checks and failures explicitly.

Store each node's files in a new revision directory and attach evidence to the
ledger. Keep rigging and deformation validation pending until actually tested.

## Local AI Lab workflow

For a case-specific open-ended edit/review loop, use `three-d-ai-lab` as the
session runner. The executor below remains useful for explicit assembly configs;
it is not the general Lab's planner or visual reviewer.

For the local equivalent of a reference-driven assembly/edit/inspect loop, use
[the executor contract](references/local-lab.md) and `scripts/lab.py`.
The calling agent reads the reference and renders, chooses transforms, diagnoses
failures and writes the next configuration. The Python runner executes that plan;
it does not understand natural language or autonomously discover anatomy.

Render a transform-only baseline first. If reviewed evidence requires garment
deformation, use an explicit fit profile on the garment, with the body protected.
Keep each failed candidate and its diagnosis; rerun into a new revision directory.
Do not hide or delete the body to make an intersection check appear to pass.

Missing inputs may be tested in a clearly labeled partial assembly branch. Do not
mark the original complete-character ledger accepted or bypass its upstream gates.
Do not describe this Blender-based implementation as Tripo's AI 3D Lab service or
as a reproduction of its proprietary Astra implementation.
