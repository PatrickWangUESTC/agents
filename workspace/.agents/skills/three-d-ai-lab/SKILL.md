---
name: three-d-ai-lab
description: Operate a local 3D AI Lab for case-specific Blender inspection, assembly, repair and revision, with preserved checkpoints and visual review. Use for agent-driven edits to existing 3D assets, including AI 3D Lab and Astra-style workflows.
---

The calling agent supplies visual reasoning and Blender Python; the local runner
executes and records each revision. This is our own implementation of the public
workflow, not Tripo's service or an embedded Astra model. Inherit the caller's model.
Current scope is asset inspection, static assembly/alignment, local repair,
detail edits, splitting/replacement and preview/revision. Do not add rigging,
facial expressions or animation to a Lab task unless separately requested.
Inventory existing rigs/morphs only to preserve them.

First read the available repository workflow (or the mapping below when working
outside this library) and the case's actual inputs. Write a case
workflow before editing: source assets, reference, goal, current checkpoint,
protected objects/properties, dependencies, permitted operations, required checks,
and stopping condition. Reuse existing generated meshes; do not start generation
or introduce facial control merely because a tutorial includes those stages.

Read [the runner contract](references/runner.md) to initialize and operate a Lab.
For an agent-driven iteration, read [the observation/action loop](references/agent-loop.md):
use observe to gather file-bound scene and image evidence, inspect those images,
then submit a bounded diagnosis/operation through act. Re-observe after each result.
For local mesh defects, read [repair decisions](references/local-repair.md).
For reference-driven color-only changes, use character-material-refinement; protect
all geometry and UVs and inspect the actual anatomical mask.
Read [the Tripo mapping](references/tripo-mapping.md) when selecting a workflow.

1. Observe the baseline inventory AND reference/preview images. Confirm actual
   object names, UVs, morphs, bones, materials and coordinate system. Mesh statistics
   do not establish surface quality or semantic parts.
2. Diagnose one concrete defect against current evidence. Record the relevant
   object/view, intended operation, protected properties and pass condition in a
   diagnosis file. Choose a case-specific operation, not a hard-coded color rule.
3. Write a Blender Python operation and run it on a new revision. Existing assembly
   and delivery helpers may be used when their preconditions match. Generated code
   runs with local process permissions; the runner is not a Python sandbox.
4. Read the inventory, protected-property checks and native-file readback. View the
   newly rendered images. Add close-up/pose/material/export evidence using the
   operation when the case needs it; default previews are neutral geometry only.
5. Submit an evidence-bound review. Promote only when this case's required checks
   pass. Rejected/failed candidates never replace the selected checkpoint; next
   run defaults to that selected checkpoint. Retain failure diagnosis.

The Lab's selected revision is scoped to its case goal. It does not accept an
upstream complete-character ledger or prove collision freedom, topology quality,
facial animation, export quality, or engine readiness unless separately tested.
No subagents are required. Describe sequential self-review honestly.

When the user requests downstream delivery, hand the selected immutable checkpoint
to character-canvas `pipeline.py from-lab` and character-delivery. Preserve this Lab's
static scope and keep downstream acceptance separate. Optional replacement is only
for requested parts; assembly/intersection review must precede binding. A passing
inspection-task review must never bypass failed asset-quality checks.

For separately requested downstream operations, route optional part upgrades to character-part-upgrade, full-part binding to character-rigging and skeleton FBX delivery to character-fbx-export. Existing fused parts need a reviewed split before the static replacement helper; do not broaden a static Lab task automatically.

For static inter-part crossing requirements, declare geometry_checks.surface_pairs
in the case so the worker measures crossings before and after fresh-process readback.
A failed machine check blocks acceptance; an agent cannot override it with pass text.
Zero detected crossings is still limited evidence: inspect local topology, cuff/seam
openings and visual quality. Closed sleeve caps and fused geometry may require local
reconstruction; nearest-normal projection is not a universal repair method. Never
relax displacement limits or remove unrelated surfaces just to pass a metric.
