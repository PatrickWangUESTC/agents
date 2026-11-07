---
name: character-fbx-export
description: Export a complete skinned character to skeleton FBX and verify its hierarchy, skinning and posed surfaces in a fresh Blender process.
---

Use for a requested skeleton FBX from an existing bound character. Read the current
brief and rig/pose evidence; a successful export does not accept failed deformation
or intersections. Keep the native .blend and source textures. Include every mesh
and the intended skeleton; never silently export a body without clothing or shoes.

Read [the export contract](references/execution.md). scripts/export_fbx.py checks
part inventory and skinning, exports FBX with no added leaf bones, then launches a
fresh Blender process to import it. It checks bone names/parents, material slot
identities, UV/triangle counts and sampled rest/deformed surfaces. Diagnostic poses
must move geometry, and their tolerance is expressed in scene units.

This helper exports the skeleton and skin only, from a reviewed rest checkpoint.
It rejects non-rest pose offsets instead of silently changing the current stance. It rejects active animation/NLA
and constrained rigs; preserve the original and prepare a reviewed deform-only
checkpoint or use a separate animation-aware exporter. It does not silently discard
clips, bake arbitrary control rigs or claim facial/engine compatibility.

Inspect original-material native and reimported views separately. FBX material and
shader/texture appearance is not certified by slot names; examine textures and
record any conversion differences. Check dimensions/axes in the intended consumer.
Retain config, source hashes, exporter snapshot, FBX hash, readback log and report.

Update character-canvas export and roundtrip nodes only with their required checks.
Use the fresh-process report for its bounded structural/surface claims; material
appearance and visual acceptance need additional evidence. A fail or missing report
is not accepted. Other requested formats remain character-delivery responsibilities.
Engine validation stays not_run for Blender-only requests. No engine or facial
animation acceptance follows from a passing FBX roundtrip.
