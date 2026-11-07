---
name: character-part-upgrade
description: Upgrade a requested character part such as a head using a new reference or mesh, preserve unaffected parts, and hand the reviewed replacement to rigging.
---

Use only when the case requests a local upgrade. An optional workflow node is not
permission to replace the face. Record the defect, target objects/region, identity
reference, immutable source and expected improvement. Preserve the current best
checkpoint; generation failures do not justify replacing unrelated parts.

Inspect whether head, hair and neck are separate objects or fused into the body.
For fused meshes, use an explicit reviewed segmentation/mask and the 3D AI Lab
before replacement. Do not delete a whole body object to replace a head or infer
part membership solely from height. A generation provider's named part is still
an unverified candidate.

If no replacement mesh exists, prepare a part reference with the available image
tool, preserving identity and view consistency, then use an actually available
mesh-generation provider. Save job handles and original mesh/texture outputs.
Do not regenerate when the case already supplies a usable candidate.

For separated static objects, read [the execution contract](references/execution.md)
and use scripts/upgrade.py inside Blender. It imports a .blend or .glb candidate,
applies explicit placements and saves a new checkpoint with non-target mesh-state
signatures. It does not infer alignment, weld neck seams, transfer rigs or generate
an image. Existing morphs, skinning or modifiers require a dedicated transfer path.

Use the Lab for fixed-camera before/after original-material views and face/neck
close-ups. Check face identity, hair silhouette, neck seam/gaps/intersections,
scale, UV/material fidelity and unaffected parts separately. A successful script
produces a candidate; it cannot accept visual improvement or collision freedom.

Record requested_part_replaced, unaffected_parts_preserved and visual_review in
the character-canvas local_upgrade node only with current file-bound evidence.
Then redo assembly_review. Changed topology invalidates affected rig/skin/morph
and export evidence. Pass the accepted new checkpoint to character-rigging;
keep the old checkpoint and rejected candidates available.
