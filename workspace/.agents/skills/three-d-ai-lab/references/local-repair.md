# Case-specific local surface repair

Start from the latest appropriate mesh checkpoint, not generation. Freeze accepted
parts and preserve immutable source assets. Record actual object names, units, axes,
pose, region bounds, tolerances and intended contacts before editing. Derive those
from this scene; meters, an A-pose, bilateral symmetry and a body/clothes/shoes split
are not universal assumptions.

## Diagnose before displacement

Use native-material full views and local orthographic/oblique views. Inspect the
underlying triangles and topology as well as colors: an apparent dark patch may
be albedo, a surface crossing, a closed cap or missing geometry. Establish which
surface is intended to remain outside and which part may change. For fused body,
hair or layered garments, combine connected components, UV/material islands and
anatomical evidence; a nearby point or a single albedo threshold can select hair.

Choose the least invasive suitable operation:
- Misalignment: correct the explicit transform before deforming vertices.
- A few shallow local crossings: bounded displacement with protected boundary,
  smooth falloff and a case-scaled clearance, then check folds and silhouette.
- A closed sleeve/boot cap through a limb: inspect boundary topology. If warranted,
  locally remove the wrong cap and reconstruct an actual opening joined to the
  retained boundary, preserving the visible contour and transferring texture.
- A color defect without geometric error: use character-material-refinement.

Nearest-normal projection is not a universal repair. Repeatedly pushing vertices
can fold the patch or distort the silhouette even when a crossing count decreases.
When bounds are exceeded or appearance worsens, revisit topology/segmentation rather
than increasing displacement or relaxing the acceptance threshold.

## Reconstructing an opening when justified

Confirm how many boundary loops exist and their winding/manifold status. Preserve
retained mesh coordinates within numerical tolerance. Map old/new boundary vertices
with minimal circumferential distortion; arc-length-to-circle mapping can twist an
asymmetric outline. Inspect the tangent transition and any hem/inner return: a folded
lip can intersect its own outer wall. Openings are intentional boundaries, not holes
to cap blindly. Complex multi-layer/non-manifold boundaries need another strategy.

Transfer UVs or bake from the preserved source with explicit misses/coverage checks.
Do not assume shared UV islands are unique. A geometrically clean seam can still
show a visible material discontinuity; inspect both and report remaining differences.

## Acceptance evidence

Use fixed world-space regions and pair names declared before repair. The built-in
checker clips confirmed intersection segments to those regions; zero is only a
static noncoplanar surface result for those pairs. Separately check rebuilt patch
self-crossings/old-surface crossings, degeneracy, boundary connectivity and edit
locality. Record adjacency exclusions and numerical tolerances. Nearest-vertex gap
samples are not a guaranteed minimum surface separation.

Render original and candidate with identical camera, light, material and display
settings. Inspect complete front/back/left/right plus affected closeups, including
hidden-side openings. Rejected candidates stay in the history; do not promote a
numerical pass with visible folds, protrusions or changed protected anatomy.

Save/reload the native scene in another process. If exporting, reimport and compare
part inventory, material values/textures, surface samples and the same scoped checks;
inspect exported views too. A local cuff pass does not accept the torso/shoes, an
entire character, or poses not tested. Topology changes invalidate downstream weights
and morph correspondences even when object names remain the same.
