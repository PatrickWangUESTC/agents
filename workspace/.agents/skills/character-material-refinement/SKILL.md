---
name: character-material-refinement
description: Correct reference-driven colors on explicit character surface regions, including exposed skin, while preserving geometry, UVs, facial details and non-target materials. Use after mesh assembly or for a material-only revision.
---

Inspect the reference and current native-material views before choosing regions.
Distinguish a color defect from a missing surface, intersection or geometric ridge;
recoloring cannot repair geometry. Keep geometric edits in three-d-ai-lab.

Use three-d-ai-lab to branch the latest appropriate checkpoint. Protect geometry,
UVs, transforms and existing rig/morph state of every affected or neighboring mesh.
Detect shared mesh/material data before assignment. Never recolor a whole fused
body/hair object just because its name says Body.

Prepare explicit face masks for this mesh, using inspected anatomy, connectivity,
material/UV islands and reference evidence together. Bounding boxes and color
thresholds are candidate selectors, not semantic truth. Inspect mask overlays or
native previews at boundaries, including hair near the neck and hidden-side skin.
Do not reuse another character's coordinates, hair color or face indices.

Read [the material contract](references/materials.md). The Blender helper applies
hash-bound face masks and reviewed sRGB colors, copies shared mesh data/materials,
and reports geometry/UV preservation. It does not segment anatomy or judge a mask.
Color sampling and any face-relative calibration are explicit case decisions.
Keep original samples, crop locations, color-space assumptions and the mapped
material values. Prefer direct transfer first; calibrate only when scene evidence
shows an appearance mismatch, preserving reference regional differences.

Review same-camera full views and affected closeups in the native material render.
Keep facial features, hair, clothing and accessories outside the selected regions.
Export if requested and verify material values/textures in a fresh process, then
inspect reimported renders. Report color acceptance separately from geometric and
animation acceptance. Original geometric ridges may remain after a color-only edit.
