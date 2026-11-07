---
name: character-delivery
description: Verify character rigging, export round trips, and actual target-engine behavior before reporting a character ready for animation or game use.
---

Read the actual delivery brief. Rig only with a real available tool, preserving
the pre-rig checkpoint and recording tool/version, joints, weights and limitations.
Test rest and representative deformed poses. Check required joints, skin weights,
clothing behavior, penetrations and any facial morphs independently.

Save native .blend, textures and build/edit scripts. Export the requested format
and re-import into a fresh Blender process or clean scene. Verify semantic parts,
materials, dimensions, skeleton, weights and requested animation clips. A file
extension, skeleton screenshot or successful export does not establish animation.

For a game-ready claim, actually import into the requested engine, apply the
intended animation and verify the requested behavior. Capture engine/version and
evidence. If the engine is unavailable, mark engine validation not_run and deliver
the available files with that scope. Never relabel a round-trip check as engine
acceptance. Update the ledger only with evidence tied to current artifact hashes.

When the user supplies a reference skeleton, inspect the owning template and its
active runtime selection first. A repository may retain incompatible historical
templates; a nearby bone-name list is not proof of the current skeleton. Preserve
the reference names and parent map, record its hash, and distinguish adapted joint
positions from the source rest pose. Do not replace the user's requested skeleton
with a generic convenience rig. Preserve current geometry while fitting the rig.

For explicit case-specific FK binding, `scripts/rig_blender.py` accepts reviewed
bone endpoints, optional roll axes and semantic aliases. It creates normalized
four-influence skinning, diagnostic actions, renders, a native scene and exports.
Its current color/region policy targets a purple-haired, gray-suited A-pose input;
it is not a universal autorigger. Frozen config/scripts belong with each revision.
Use `scripts/verify_rig.py` on an output directory for clean GLB/FBX imports and
posed-surface comparisons against the native file. The importer may create bone
display widgets; exclude only actual custom-shape objects, not arbitrary meshes.

Hair/skin fused surfaces can stretch despite normalized weights and correct
hierarchy. Record failed poses and keep a candidate marked unaccepted when these
remain. Smooth or constrained weight experiments must be compared at the same
pose; do not declare improvement from the rest frame. User-requested Blender-only
validation leaves engine validation pending and does not authorize engine setup.

For post-Lab continuation, execute only eligible nodes in the character-canvas ledger:
assembly_review -> rig -> pose_test -> export -> roundtrip -> optional engine.
A selected Lab inspection revision does not prove assembly acceptance. The current
rig_blender.py policy supports body + clothing only; rig_preflight.py rejects unlisted
scene meshes and unsupported extra parts before binding. For a character with shoes,
implement and verify explicit all-part binding before running that policy. Do not
silently drop shoes, reuse an older scene's rig acceptance, or mark engine passed
when the case is Blender-only. Facial controls remain a separate explicit scope.

The new character-rigging skill provides a separate complete-inventory binder with automatic/explicit weights and rigid attachments; the older two-part case script remains unchanged. Use character-fbx-export for skeleton-only FBX and a fresh-process posed-surface check. Its report does not validate shader appearance, animated clips, visual deformation or intersections; keep those checks explicit.
