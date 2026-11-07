# Local assembly executor

The agent supplies a reference, named GLB parts, an instruction and an explicit
configuration. Blender performs static assembly, renders native materials and
part colors, saves a native scene, exports GLB and imports the export in a clean
scene. The agent then reviews the current renders and proposes a local revision.
No Tripo/N4D API requests are involved. Requires an installed Blender with NumPy;
the initial actual character run uses Blender 4.3.2.

Run from a task workspace:

```bash
python3 .agents/skills/character-assembly/scripts/lab.py inputs/assembly.json \
  --out artifacts/assembly/r01 --blender /path/to/blender
```

`--validate-only` checks inputs and effective source hashes without starting
Blender. An existing output directory is rejected. Relative input paths resolve
against the configuration file. Each output contains a frozen config, executor
snapshot, execution log, status, `.blend`, `.glb`, eight review images and an
inspection report. Status `produced` means the execution completed, not acceptance.

Configuration example (values are illustrative, not a universal character fit):

```json
{
  "schema_version": 1,
  "instruction": "Assemble the supplied parts against the reference; keep the body unchanged.",
  "reference": "reference.png",
  "display_height_m": 1.65,
  "missing_parts": ["shoes"],
  "parts": [
    {"name": "body", "source": "body.glb", "protected_geometry": true},
    {"name": "clothing", "source": "clothing.glb",
     "scale": [0.8, 1.0, 0.8], "translation": [0, 0, -0.1],
     "rotation_degrees": [0, 0, 0]}
  ]
}
```

Transforms apply in Blender's imported Z-up coordinates. `scale` may be
nonuniform. `display_height_m` scales the entire result for presentation; it is
an assumption, not a measured physical height from the reference image.

For reviewed local fitting, a part may have `fit_profile` rows of
`[source_world_z, x_scale, y_scale, x_offset, y_offset]`. Parameters interpolate
linearly between strictly increasing heights and clamp outside them. This changes
vertex positions before the part transform, while preserving topology and UVs.
It is a broad shape-fitting control, not cloth simulation, collision solving or
automatic landmark recognition. Protected geometry rejects this option. Keep
skinned/morph-equipped assets out of this static deformation path.

An optional `surface_clearance` on the editable garment provides bounded
nearest-surface displacement against a named static part. Example:

```json
{"target": "body", "margin": 0.015, "max_displacement": 0.14,
 "iterations": 3, "smoothing_cell": 0.025,
 "target_filter": "neutral_albedo", "max_channel_ratio": 1.4}
```

Distances are in the assembly coordinate space before presentation scaling.
Projection uses oriented face normals and may fail on open, noisy or inconsistent
geometry. A smoothed displacement field reduces pointwise spikes; it does not
establish collision freedom. Inspect every result, including the back. The optional
`neutral_albedo` filter is specifically useful for a gray suit and colored hair;
it samples a directly connected base-color image and retains near-neutral faces.
It is not semantic segmentation and must not be used on arbitrary body textures.
Omit it for a clean body-only collider. Clipped projections and negative-side
vertex counts are diagnostic observations, not a complete penetration measure.

For a small defect identified in current views, `local_offsets` accepts entries
`{"center": [x,y,z], "radius": [rx,ry,rz], "delta": [dx,dy,dz]}`. Each applies a
Gaussian-weighted displacement after surface fitting, in the assembly coordinate
space before presentation scaling. Protected parts reject it. Recheck all views
afterward; a front-view fix may introduce a back-view intersection.

The generated character trial preserves a failed transform baseline and failed
raw projection, rather than claiming every fitting operation improves the asset.

Write `visual-review.json` beside the current candidate, naming current image
paths, observed defects, protected properties, scope and next operation. Hash
checks do not prove silhouette, garment clearance, interiors or deformation.
When a candidate improves, report the remaining defects rather than making all
checks pass. Missing shoes, rigging or unresolved intersections stay explicit.

For multiple assets, use the repository's existing isolated batch launcher with
one input/config directory per character. The agent uses this skill inside each
workspace; each revision writes a fresh directory. Do not run independent Blender
processes against the same output file.
