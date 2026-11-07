# Material-only operation

Run inside the three-d-ai-lab operation (the runner supplies `OUT`). Resolve the
helper from this workspace's skill directory; do not embed a developer's home path.

```python
import runpy
helper = runpy.run_path('/absolute/workspace/.agents/skills/character-material-refinement/scripts/material_edit.py')
helper['apply']('/absolute/case/materials.json', OUT)
```

A config names actual scene objects and a fingerprint of each target mesh. Obtain
that fingerprint with `helper['fingerprint'](bpy.data.objects[actual_name])` during
inspection. Recompute masks after topology changes; a matching object name is not
sufficient. Freeze config and masks with the action evidence.

```json
{
  "regions": [{
    "name": "exposed_forearm",
    "object": "CharacterSurface",
    "mesh_sha256": "SHA256_FROM_CURRENT_MESH_FINGERPRINT",
    "faces": {"path": "forearm-faces.json", "sha256": "SHA256_OF_MASK_FILE"},
    "color_srgb": [0.82, 0.62, 0.50],
    "color_evidence": "Corresponding reference crop; describe direct sample or reviewed calibration"
  }]
}
```

The mask is a nonempty JSON array of unique polygon indices. Paths are relative to
config. Overlapping region masks on an object are rejected. Values above are schema
illustrations, not skin defaults. The helper supports static meshes without modifiers
or morphs; preserve an existing rig with a separately reviewed material-only path.
It validates every region before changing scene state. Each source material used
by a mask must have one Principled BSDF feeding the active Material Output Surface
directly. Unsupported shader graphs fail rather than silently dropping effects.
The helper copies each target mesh once and each affected source material per
region, changes only Base Color, and retains other shader inputs. A constant sRGB
color is converted to scene-linear RGB; procedural sampling/baking is not implied.

Reference workflow:
- Identify corresponding skin/fabric regions in the actual reference. Record image
  hash, sample boxes/polygons, representative colors and excluded outlines/highlights.
- Direct sampled albedo and rendered appearance are different under lighting/tone
  mapping. If needed, use the current face or another accepted material as an anchor;
  record the original sample, anchor and mapping, and keep eyes/lips/linework intact.
- Select exposed anatomical surfaces, with a small hidden overlap under garments if
  needed. Inspect connected islands when hair and body are fused in one object.
  A purple-hair/gray-suit mask is not transferable to a different character.
- Keep original images and materials. For texture painting, make image copies and
  check UV overlap so one skin patch does not recolor another part sharing the atlas.
- Compare both sides and back, checking remaining gray islands, abrupt boundaries,
  lost details and changed non-target parts. An execution report is not visual QA.

Outputs inside the revision: `material-edit-report.json` and `material-inputs/`
with the exact config and masks. The report binds colors and mask hashes, and records
unchanged geometry/UV/transforms. GLB/FBX roundtrip and visible quality remain separate
checks; a mask can be structurally valid and semantically wrong.
