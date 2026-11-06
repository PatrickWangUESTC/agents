---
name: mesh-generation
description: Generate a mesh through the configured provider, resume an existing remote job, retain the original, and inspect native part assets for the character pipeline; optionally derive a lowpoly candidate only when requested.
---

Use scripts/generate.py for the N4D adapter. The stable handoff is job.json with
provider, job_id, request, status and artifact path/hash. Read credentials from
N4D_API_TOKEN or ~/.config/agents-providers/n4d.token, never from a checked-in file.
The adapter supports text-to-model and image-to-model, one candidate and
disablePbr=1 (PBR off; base-color textures may still be present). Tripo is a future adapter, not implemented here yet.

For image input: `prepare-image --image <file> --out <new-job-dir> --execute`
preserves the original, uploads to matting, saves its request ID, resumes that
request on repeated calls and downloads the first prepared image as matted.png.
Inspect matted.png before `generate-image --out <job-dir> --execute`. It uploads
that image as multipart image with modelCount=1 and disablePbr=1. A live request
on 2026-11-06 established this contract: the older PDF's JSON fileKey submission
was explicitly rejected with HTTP 400 (Image file is required). Do not retry
that obsolete contract or silently replace the reference with a text prompt.
Keep the provider's pointsDeducted and generationConfig receipt when returned.

Run balance first. `generate --prompt-file ... --out ...` only prints a plan;
`--execute` submits one billable task when the user has authorized generation.
Persist the handle, then poll with a bounded timeout. `resume --out ...` only
continues that job. Never resubmit after a timeout, ambiguous response or missing
receipt; reconcile provider history if submission status is uncertain. Keep one
writer per job directory. Original download files are immutable inputs to edits.

For a posed/cropped character image, first use the image generation capability to
produce and inspect a complete front A-pose. Extract separate clothing, shoes and
body (including head/hair) reference images from that canonical image, then submit
one model per group. Preserve source and generated references with prompts/hashes;
label inferred hidden regions. Put stockings in clothing unless specified otherwise.
No forced lowpoly target: keep triangle_budget=null unless the user sets a budget.
Use inspect_blender.py for native GLB inventory, unmodified geometry previews and
a separate .blend. Do not run lowpoly_blender.py as a default generation stage.
Serialize N4D submissions per account. A live service response can say
"Your task is already being processed, please submit again later" even for
matting. Keep that response; resume the active task to completion before another
explicit submission. Missing task IDs without a clear rejection remain uncertain.

The documented legacy endpoint does not establish native Smart Mesh controls.
Do not invent topology/polycount parameters from web UI settings. For a lowpoly
delivery, preserve the original, then run scripts/lowpoly_blender.py in a fresh
Blender process to derive a separate candidate. Default budget is 5,000 triangles.
Label that candidate locally decimated, not native quad/Smart Mesh generation.
Inspect current front/side/back/three-quarter renders and the budget/roundtrip
report. A budget pass does not prove silhouette quality or deformable topology.
Compare an original-mesh render under the same camera and light before attributing
artifacts to generation. On a measured fragmented-source failure, an explicit
`--voxel-resolution 500` branch may reconstruct a geometry-only surface before
decimation. This changes geometry/UV/rig correspondence and must not overwrite the
source or inherit its acceptance. Keep failed budget and visual variants. Imported
custom normals are cleared on the derived candidate after collapse; validate mesh
data before export, then verify the actual reimported triangle count. Always pass
Blender `--python-exit-code 1` so a Python exception cannot look like process success.

Record real generated assets in a character node only after upstream references
or the text brief have been validated. A job download alone remains produced;
use current hashes and appropriately scoped evidence for acceptance. Keep rig,
animation, collision and target-engine checks pending unless actually executed.
Future provider adapters must keep the same job/artifact contract, explicit model
and options, no-duplicate-submit behavior and separation of production/acceptance.
