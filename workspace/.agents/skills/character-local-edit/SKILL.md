---
name: character-local-edit
description: Replace or refine a named character part, such as the head, with a revision branch and before/after checks that protect non-target geometry, materials, UVs, and rigs.
---

Write the target part, observed problem, reference evidence, edit scope and pass
condition. Fork the character-canvas ledger for that part. A generation change
invalidates assembly and downstream evidence; a reference change also invalidates
that part's reference-preparation evidence. Reuse the other parts' source files.

Save a separate baseline scene. Inventory non-target object transforms, mesh data,
material assignments, UVs, shape keys, armature and relevant modifiers. Detect
shared data before edits; make a local copy if the target shares resources.
Keep head/hair/neck membership explicit rather than inferring it from proximity.

Replace or edit only the target in a new scene revision. Preserve protected state
unless the task explicitly authorizes broader change. Re-render identical views
and compare non-target signatures. Inspect the attachment seam, penetration and
silhouette; add geometry-specific checks when needed. If a preservation check
fails, keep the old checkpoint and reject the candidate.

Changed topology invalidates rig/skin/morph correspondence. Re-run the affected
binding and animation checks; do not reuse old acceptance merely because object
names match. Retain both candidates and their evidence for review.
