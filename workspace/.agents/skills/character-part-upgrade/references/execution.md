# Static replacement contract

Run with a new output directory:

```bash
"$BLENDER_BIN" -b --python-exit-code 1 --python /path/to/character-part-upgrade/scripts/upgrade.py -- /absolute/upgrade.json /absolute/new-revision
```

Config fields:
- `source`: `{path, sha256}` of the original .blend.
- `targets`: exact separated mesh object names to remove from the new checkpoint.
- `candidate`: `{path, sha256, objects}`; `objects` names the objects to append from
  a .blend. For .glb, all imported objects must be standalone static meshes.
- `placements`: mapping of every imported object name to an explicit 4×4 world
  matrix, including scale. Use inspected transforms; no automatic fitting occurs.
  Blender may suffix an imported name when it collides; prepare distinct candidate
  names before running instead of guessing a renamed object.

Source and candidate hashes must match. Existing files are not overwritten.
Unsupported inputs fail rather than stripping weights or shape keys. The helper
protects mesh coordinates/topology, UVs, per-face material assignments, material
slot identities and world transforms of other meshes. It does not certify full
shader/texture equivalence; inspect native-material previews separately.

Outputs: candidate.blend, upgrade-report.json, config.json and the executed script.
Report checks for seam/intersections/visual review start as not_run. Use a Lab
session for additional edits and visual review; do not change these to pass from
file existence alone. Retain the failed output directory and retry in a new one.
