# Agent → Blender → feedback loop

The calling Codex agent is the reasoning and image-inspection component. Blender
is the mesh execution and rendering component. This reproduces the observable
workflow with headless local Blender; it does not embed Astra, claim Tripo's private
implementation, or add a separate hidden model API. The same model decides the
next bounded operation after reading fresh evidence. No subagents are required.

## Observe

```bash
python3 scripts/lab.py observe /absolute/lab --out /absolute/observation-01.json
```

The packet pins the session, case, selected checkpoint, observed scene, receipt,
image hashes, inventory and machine checks. It includes the latest failed/rejected
revision's log/review pointer. Read actual images with an image-view tool; paths or
hashes alone do not constitute visual inspection. A supplied `--revision rNNNN`
can inspect a specific produced candidate; selection remains unchanged.

## Diagnose and act

Write a decision JSON with:
- `observation`: path to that saved packet, relative to decision JSON or absolute.
- `observation_sha256`: exact packet hash.
- `operation`: Blender Python script path, relative to decision JSON or absolute.
- `operation_sha256`: exact operation hash.
- `diagnosis`: observed defect, its evidence and proposed cause.
- `edit_scope`: named object/region, permitted change and displacement/topology limits.
- `expected_improvement`: measurable or visually assessable effect.
- `stop_condition`: acceptance conditions and conditions requiring a changed approach.
- `viewed_images`: actual image paths from the packet inspected by the agent.

```bash
python3 scripts/lab.py act /absolute/lab --decision /absolute/decision-01.json
```

The tool rejects stale observations, changed selected checkpoints, altered scripts
and missing image references. It freezes packet, decision, script and diagnosis in
an action directory before running a new revision from the observed checkpoint.
It cannot prove that an agent actually looked at the images; the agent remains
responsible for doing so. The JSON does not itself perform reasoning or choose edits.
The legacy `run` command remains available for explicit manual operations.

## Verify and review

For static inter-part surface checks, declare this in the initial case:

```json
{
  "geometry_checks": {
    "surface_pairs": [
      {"objects": ["Body", "Clothing"], "max_crossings": 0},
      {"objects": ["Body", "ShoeLeft"], "max_crossings": 0}
    ]
  }
}
```

These optional checks run after the operation and again after loading the saved
scene in a separate Blender process. The worker uses BVH broad phase and independent
triangle-plane/edge segment confirmation. Crossings over 1e-7 scene units count;
thresholds apply per explicit pair. A result exceeding the configured threshold
sets the structural checks to fail, so `review` cannot accept it even when a caller
submits pass text. Missing or unsupported named meshes fail execution. Checks apply
to static meshes without modifiers or morphs; pose-conditioned checks need a separate
reviewed evaluated checkpoint.

For a local repair, a pair may also declare an immutable world-space bounding box,
for example `"region": {"min": [-1,-1,0], "max": [1,1,2]}`.
These coordinates illustrate the schema; derive bounds from the current scene.
Only the length of the confirmed intersection segment inside that box counts.
Declare the region before editing and retain it for before/after and saved-scene
checks. A local pass applies only to that region; it must not unlock whole-character
assembly, rigging or dynamic acceptance. Check the rebuilt patch for self-crossings
separately, and inspect consistent native-material views and cuff closeups.

The check proves only its declared surface-crossing scope. It does not certify
coplanar overlap, solid containment, penetration depth, self-intersections, motion
or visual quality. Zero crossings never substitutes for examining cuff openings,
neck seams, silhouettes, textures or folded/degenerate faces. Do not delete or hide
surfaces simply to force a zero count. Existing cases lacking the declaration do
not retroactively gain these checks: branch a new case/session.

Read native-material close-ups and consistent full views after editing, not just
the default neutral previews. Then use the existing `review` command. Rejections
retain the selected checkpoint; execution failures do likewise. Run `observe`
again before the next act. If multiple attempts worsen the shape or exceed local
bounds, re-examine segmentation, caps and local topology instead of increasing
projection strength or relaxing the acceptance limit.

The current sleeve case demonstrates why this matters: naive surface-normal
projection introduced folds; an overly broad arm region included unrelated points.
Those attempts are failures, not reusable automatic garment repair methods.
