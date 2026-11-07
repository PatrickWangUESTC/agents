# Skeleton-only FBX export

```bash
"$BLENDER_BIN" -b --python-exit-code 1 --python /path/to/character-fbx-export/scripts/export_fbx.py -- /absolute/export.json /absolute/new-export
```

Config:
- `source`: `{path, sha256}` for the actual rigged .blend checkpoint.
- `parts`: exact names of ALL mesh objects; the scene must have one armature.
- `diagnostic_poses`: nonempty list of `{bone, axis, degrees}`. Axis is world X/Y/Z.
  Use representative joints (e.g. head, root/hips, left ankle, right ankle). Each
  test resets to rest, rotates one bone in world space and must move sampled vertices.
- `tolerance_scene_units`: optional positive tolerance <= .01, default .0001.
  Interpret it against actual scene scale; do not call scene units meters blindly.

Input must already be in the reviewed rest pose (identity pose offsets); otherwise
the tool rejects it rather than resetting a user-selected stance. Input must have normalized 1-4 deform influences per vertex and an armature modifier
on every mesh. Active actions/NLA and constraints require a separate reviewed bake
path. Export uses selection of all meshes plus armature, -Z forward/Y up, unit scaling,
no synthetic leaf bones, no animation bake, and requests embedded textures.

Output: character.fbx, baseline.json, roundtrip.json, readback.log, config.json and
export_fbx.py. Reimport checks run in a new Blender process (600-second limit), not
in a polluted scene. A failed export/readback keeps the diagnostic directory and
exits nonzero; retry into a new directory. Every file is a candidate until reviewed.

The comparison uses roughly 4096 sampled source vertices per part/pose, nearest
imported vertices and complete world bounds. It tolerates FBX vertex splitting,
but does not prove a full topological bijection. Bone hierarchy, mesh/material-slot
identities, triangle counts, UV-layer counts and normalized weights are checked.
Shader/texture pixels, animation clips, collisions and engine playback are not.
