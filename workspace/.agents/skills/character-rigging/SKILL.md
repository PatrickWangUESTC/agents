---
name: character-rigging
description: Bind all character parts to an explicit or reference-matched skeleton in Blender, support rigid shoe attachments and verified skin weights, and test rest and deformed poses.
---

Start from the current accepted assembly checkpoint. A completed Lab inspection
is not assembly acceptance. Preserve the source mesh, surface, UVs and current
leg/arm pose; do not force a different stance to simplify binding. Inventory every
mesh, existing rig, weights, shape keys, modifiers and actual coordinates first.

Inspect the user's reference skeleton and its real owning template. Preserve
requested names and parent hierarchy. Fitted joint endpoints and roll are explicit
case choices; record them separately from reference rest positions. Do not reuse
another case's pose acceptance or invent a universal automatic joint detector.

Read [binding and pose contracts](references/execution.md). scripts/bind.py accepts
reviewed world-space bones and a policy for every mesh: Blender automatic heat
weights, an explicit normalized per-vertex weights file, or a rigid attachment to
a named deform bone. No scene mesh may be omitted. The skeleton reference, when
supplied, is loaded and its actual names/parents are compared against the config.

Use rigid foot attachments only for shoes that should not bend internally. Confirm
left/right by the current scene and joint locations, not names alone. Test ankle
rotation and toe-off: rigid shoes will not follow separate toe flexion. Flexible
footwear needs reviewed skin weights. Automatic heat weighting can fail on fused
hair, layered clothing or disconnected geometry; failure is not permission to use
an unreviewed nearest-bone fallback. Explicit weights must match vertex order.

The script produces rigged.blend and structural evidence, not animation acceptance.
Run representative diagnostic poses and fixed-view renders; separately inspect
body/hair attachment, clothing and shoe deformation, finger/ankle behavior when
required, and new intersections. Preserve rest geometry and reject bad deformation
even if weights normalize. No facial controls or production clips are implied.

Use character-canvas rig and pose_test required checks. Record all_parts_bound,
reference_skeleton, normalized_weights, rest_surface_preserved for rig, then
body_hair_deformation, clothing_shoe_deformation, posed_intersections for pose_test.
Only accepted candidates proceed to character-fbx-export. Existing rigged assets
need a preservation/transfer path rather than this static-input binder.
