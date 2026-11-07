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

For requested reference-to-part upgrades and separated static replacement, use character-part-upgrade. Its helper does not segment a head fused into the body; keep this edit workflow for explicit segmentation and case-specific seam repairs.

For surface intersections/openings, use three-d-ai-lab and its local-repair guide.
For a material-only defect, use character-material-refinement; do not invalidate
vertex correspondence by remeshing merely to change colors. Explicitly recheck
materials and exports while retaining applicable geometric evidence.
