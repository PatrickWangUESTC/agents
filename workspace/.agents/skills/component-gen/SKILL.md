---
name: component-gen
description: Generate independent low-poly anime character meshes and reference-matched textures from reviewed part images. Use for Component Gen, 部件生成, or continuing an extracted part or P1 mesh through Tripo Smart UV and B-version texturing.
---

Use the reviewed case-specific parts from character-part-extraction. For each part, use its individual front PNG as the geometry and color reference. The complete A-pose provides scale and alignment during assembly. Use the Tripo CLI with the authorized regional account.

## Selected models

1. Generate geometry with Smart Mesh P1, model P1-20260311. Use a default target of 5,000 faces per part, texture=false and pbr=false. Record the actual triangle count from the output.
2. Unwrap the selected mesh using Smart UV with baking disabled. Reuse an existing verified UV output when available.
3. Generate base color with B, model v3.5-20260815. Use the single front part image, original_image alignment, standard quality, seed 42, delight=true and pbr=false. Use the textured GLB for downstream work.

## CLI recipe

Set PART_IMAGE to the reviewed PNG and PART_OUT to its own output directory. Execute the requested stages in order. For an existing P1 or UV checkpoint, begin at the next required stage. Preserve the CLI JSON receipts and task IDs separately. Recover an interrupted task by its ID or CLI history before submitting another job.

```sh
set -eu
mkdir -p "$PART_OUT"
tripo generate image-to-model "$PART_IMAGE" --model P1-20260311 \
  -p face_limit=5000 -p texture=false -p pbr=false \
  --out "$PART_OUT/mesh" --json --no-open > "$PART_OUT/mesh.json"

MESH_ID=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["task_id"])' "$PART_OUT/mesh.json")
tripo mesh uv "$MESH_ID" --no-bake --out "$PART_OUT/uv" \
  --json --no-open > "$PART_OUT/uv.json"

UV_INPUT=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["task_id"])' "$PART_OUT/uv.json")
tripo files upload "$PART_IMAGE" --json --no-open > "$PART_OUT/reference.json"
PROMPT=$(python3 -c 'import json,sys; print(json.dumps({"image":{"file_token":json.load(open(sys.argv[1]))["file_token"]}}))' "$PART_OUT/reference.json")
tripo model texture "$UV_INPUT" --model v3.5-20260815 \
  --texture-quality standard --texture-alignment original_image \
  -p texture_seed=42 -p delight=true -p pbr=false -p "texture_prompt=$PROMPT" \
  --out "$PART_OUT/texture" --json --no-open > "$PART_OUT/texture.json"
```

For a UV task owned by another account, set UV_INPUT to its downloaded UV GLB and upload the reference with the active account. After local-file submission, check both triangle positions and per-corner UV coordinates in Blender. Frieren's boots and broom retained their triangle counts while failing exact correspondence checks. Keep each texture paired with its own output GLB.

Review the textured mesh in front, side and back views under flat lighting against the part image. Inspect hair highlights, face placement, skin tone and garment layer boundaries. Record the input and output file hashes, model versions, task IDs, actual triangles and review results for each case.
