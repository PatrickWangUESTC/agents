# Binding contract

```bash
"$BLENDER_BIN" -b --python-exit-code 1 --python /path/to/character-rigging/scripts/bind.py -- /absolute/rig.json /absolute/new-rig
```

Config:
- `source`: `{path, sha256}` for a static .blend, without pre-existing mesh parents,
  armatures, modifiers, weights or morphs. Preserve unsupported state via another
  reviewed path rather than deleting it to satisfy this tool.
- `bones`: nonempty array of `{name, parent, head:[x,y,z], tail:[x,y,z]}`. Coordinates
  are in scene world units; parents can be null. Optional `deform` defaults true;
  optional `roll_axis` is a vector used to align roll. Fit joints before binding.
- `reference_skeleton`: optional `{path, sha256, object}` of a real .blend armature.
  Required when the user specifies a template. The script compares exact names and
  parents, not positional equality; inspect and document any fit separately.
- `bindings`: mapping for EVERY scene mesh, including both shoes. Examples:
  `"Body":{"mode":"automatic"}`;
  `"ShoeLeft":{"mode":"rigid","bone":"DEF-Left ankle"}`;
  `"Clothing":{"mode":"weights","path":"/absolute/weights.json","sha256":"..."}`.

Weights JSON is one bone-name-to-positive-weight mapping per source vertex; each
row must sum to 1 with at most four deform influences. Hashing binds the weight file;
vertex-order correctness still requires provenance from the current source mesh.
Automatic weights are reduced to four strongest influences and normalized, with
adjustment counts recorded. Unweighted vertices fail. Rigid attachment is one
influence. All outputs preserve evaluated rest coordinates within 1e-5 scene units.

Outputs: rigged.blend, rig-report.json, config.json and bind.py. No morphs, simulation,
IK/control rig, automatic joint fitting or production actions are created.

## Diagnostic poses

On a copy, test required joints independently and combined (e.g. shoulders, elbows,
hips/knees, ankles, neck). Save pose definitions and original-material images. Check
rest surface and the case's specified stance separately from bone names.
Read the actual reference template to obtain bone inventory; do not inherit a
previous character's skeleton name, bone count, pose or ankle spacing.

character-fbx-export compares explicit world-axis diagnostic poses across native
and reimported FBX. That establishes sampled export behavior, not good-looking skin
or collision freedom. Existing character-delivery case-specific scripts remain
available, but their two-part policy cannot stand in for this complete inventory
binder. Dense real-character automatic binding is not proven by a small fixture.
