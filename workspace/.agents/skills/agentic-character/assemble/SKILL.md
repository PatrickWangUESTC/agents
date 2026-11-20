---
name: assemble
description: Assemble textured character parts in Blender from Component Gen or independently normalized meshes. Use for static fitting to four-view references, head/body seams, hair silhouettes, layered clothing and footwear contact.
---

## Inputs and blind trials

Start when the complete A-pose, part identities and each selected textured GLB are available. Component Gen is the local upstream skill. Use its final texture_model receipt or its paired GLB, including delight=true outputs. Match the receipt to its part and preserve its geometry, UV and base color. Resolve relative model paths using the generating workspace; pass a resolved GLB directly when moving a case. For timing, start a monotonic clock at assembly intake and stop after fresh-scene and visual review. Record reused case-specific placements and executor time separately.

For a blind trial, use the complete character reference, the fixed body and the independently centered and scaled parts in the agreed inventory. Inspect front and profile RGB renders of each textured input. Their independent framing removes the relative scale. Determine whether the body contains a continuous torso, arms, legs and feet, or only the skin exposed by the original outfit. Record which interfaces the supplied geometry can test. Keep coupled garments together. If a reference hat, belt or lining is absent, record its effect on the visible outline and evaluate the supplied pieces within the agreed scope.

Use visible landmarks on the fixed body to calibrate scale and the foot baseline. The original front image can supply fingertip positions or garment motifs. Verify both profiles for depth and the back for layer order. Check that low-contrast boots or gloves survived reference cropping by comparing with the uncropped turnaround. Keep original transforms, source assemblies and original per-part projections outside fitting. Label a resumed blind checkpoint as a resumed trial.

## Assembly loop

Use the complete character's four-view A-pose as the default assembly reference: front, one profile, back and the opposite profile. When only a front image is available, retain it and generate the turnaround from it. Record view order and provenance, check the pose, common scale and foot baseline, and use all four views during placement. In blind evaluation, reserve the original assembled geometry and its side and back renders for scoring after the candidate is frozen.

1. Inspect the complete A-pose, the individual parts and the actual imported axes. Identify the front, feet, shoulders, cuffs, hem, chin and hairline. Write a case JSON as described below. Use source coordinates of the fixed body as assembly space.
2. Run a baseline with only translations, rotations and uniform scales. Compare front, both sides and back. Inspect face readability, scalp exposure, wrists at cuffs, exposed thighs, boots, layer order and accessories. Inspect each side independently. For a pair of separately connected shoes needing distinct motion, move each whole connected shoe rigidly in a derived part file and record its transform. Keep the original asset.
3. For separate head and body meshes, apply the [mandatory neck acceptance checks](#mandatory-neck-acceptance) before handoff. The bundled neck fitter supports a star-shaped head perimeter and a closed upward-facing body cap. Adapt the local fit to the measured perimeter for other topologies.
4. Diagnose intersections on the full geometry with the complete body visible. For failed coverage or visible crossings, run the contact refinement loop. Save revisions separately and compare against the same baseline.
5. Apply the [static review acceptance criteria](#static-review-acceptance). Deliver the selected editable project, packed textures, four full views and interface close-ups after the applicable checks pass. Keep the source assets and case configuration for reruns.

## Contact refinement loop

Start from a saved baseline. Select the first failing interface, measure its coverage and inspect same-camera images. Fix gross placement with uniform scale and translation before moving local vertices. Derive garment placements and hair length from the current case's full reference views and protected meshes. Keep original layouts isolated until scoring in a blind run.

Run the contact solver on single-mesh static parts in Blender world space (+Z up, facing -Y). Supply a fresh output directory.

```sh
blender -b BASELINE.blend --python-exit-code 1 -P scripts/refine_contacts.py -- contacts.json NEW_OUTPUT
```

The configuration names the protected `body` and `head`. Optional `scalp` names the `hair` object, its cap material slots (`cap_materials`), and `reference_height_ratio` measured as crown-to-tip hair height divided by head-top-to-sole figure height. Inspect the material selection first: the cap surface should cover the crown, temples and rear; exclude trailing locks from cap measurements. The whole hairstyle moves together. Optional `placements` maps garment names to target world-space `center` and `height`. Each `clearance` step specifies a fixed `collider`, target `parts`, a clearance distance and maximum offset in fractions of collider height (`clearance`, `max_offset`), and `iterations`. Optional `height_fade: [low, high]` blends the correction from zero to full strength between those relative collider heights, e.g. to protect the fringe and ear silhouette. The solver writes a separate editable scene, reopens it and checks protected world vertices, topology, UVs and unmasked pair counts.

Recheck independently on the reopened candidate. Sample additional crown, side and rear rays between fit directions; report coverage, gap and uncovered locations. Inspect the eyes, temples, ears, cap silhouette and full strand lengths. Check the toe, heel, both sides and sole of each foot, and check the sleeve, torso, waist and skirt from multiple angles. A fall in pair counts can also mean two parts have detached. Compare the same mesh pairs before and after, identify residual contacts, and return to the last visually sound candidate when a local repair damages the design. Record the frozen revision before opening scoring data.

## Mandatory neck acceptance

For every separately assembled head and body, keep the assembly in review until both the geometry and the eight-view visual inspection pass.

- Compare the approved A-pose face, isolated head image, generated head mesh and placed head in that order. Align close-ups by eye line and eye spacing using uniform scaling. Inspect cheek width, both jaw slopes, chin tip and chin-to-collar spacing. Record the first divergent stage. A discrepancy already visible in an input returns to that stage for review. Keep the face frozen during fitting.
- Before cutting the neck, measure `neck.chin_min_z` at the lowest chin surface on the placed head in world coordinates. The complete transition band, including retry cuts, must stay below this landmark. For an older case configuration, measure this value on its own head before rerunning. Reject a visibly sharper chin even when the seam distances pass. Compare bare and dressed close-ups to distinguish geometry changes from framing and collar occlusion.
- Fit the lower neck to the actual body cross-section. Retain an existing clean opening, or remove only the redundant internal cap at the join. Match the two closed perimeters edge for edge in world space. If rebuilding a neck band, match its upper perimeter to the original head as well. Preserve the chin, face, body outside the interface, pose and other components.
- Shape the transition using the contours immediately below and above the join. Give the back and sides enough length to blend smoothly into the head. Match the visible skin color across the join.
- Reopen the saved Blender project. Verify the closed loops and their edge correspondence, sample both directions along the edges, and record the maximum gap, scene units and numerical tolerance appropriate to the character scale. Check for zero crossings outside the coincident seam, including the new neck against the collar and hair. Verify the protected geometry against the input.
- Compare bare-neck close-ups before and after from eight azimuths at 45° intervals, using identical camera positions, framing and lighting for each pair. Temporarily hide the hair, collar and other occluders and use the full unmasked body. Inspect the silhouette and skin transition in every view, especially both profiles and rear obliques. A gap, protruding cap, step, abrupt bend, visible color seam or missing check keeps the case in review and blocks handoff to rigging.

## Blender entry

Run the script from this skill directory against a new output directory.

```sh
blender -b --factory-startup --python-exit-code 1 -P scripts/assemble.py -- CASE.json NEW_OUTPUT
```

The case object contains an `apose` file path, a `body` part name, a horizontal camera direction `front`, a `frame` with XYZ `center` and orthographic `scale`, and a `parts` object keyed by name. Each part specifies either `receipt` for a successful texture_model receipt or `glb` for its final textured GLB. Paths in the case resolve relative to the case file. Each movable part additionally supplies a target world-space `height` and bounding-box `center`; optional `rotation_degrees` uses Blender XYZ Euler angles before uniform sizing. The body keeps its imported transform. This executor handles single-mesh static GLBs.

The optional `neck` object specifies the `head` part, body opening `center_xy`, two horizontal `radii`, `min_body_z` for the cap, `head_cut_z`, upper transition `blend_height`, a list of parts to `hide` in close-ups, and a close-up `frame`. All distances use the fixed body's coordinates. The executor first checks for one existing closed boundary loop near the body neck landmarks, excluding duplicate edges from UV and normal seams. It matches a valid open rim by arc length and subdivides only the rim edges to obtain corresponding segments. It tries nearby head section planes within the local neck band before attempting the closed-cap method. Verify the reopened seam and the unobstructed views even when the geometry matches.

Omit the legacy `keep_visible` option in static assembly. When resuming an older scene, remove Mask modifiers from the working copy and verify that every supplied mesh is visible in both the saved scene and the full-character renders.

When hair is a separate part, set `hair_frame` to a head-centered camera frame
and review the four head-hair close-ups. Fit the cap to the crown, brow and
temples. Long locks and asymmetric ornaments displace the whole-hair bounding
box away from the cap center. Compare matched before/after profiles for air
between fringe and forehead, check the three-quarter view for exposed scalp,
and compare the strand length and eye visibility with the A-pose.

For props that obscure the character in profile, list their part names in
`review_hide_props`. The full scene keeps all props. The additional character
views and hair close-ups temporarily hide those props. Set `review_part_colors`
to true to render four unmasked views with one solid color per part. Compare
these with the textured views to locate exposed inner surfaces before changing
geometry. For interchangeable outfits, fit the outer layer to the fixed body
and review the unmasked result before accepting the fit.

### Fitting sleeves, the back panel and paired boots

For a full-body fitting pass, keep the fixed body and foot pose visible. Compare the saved body's and head's world-space vertex coordinates
with the starting scene after reopening the revision. Keep the same camera
transforms, orthographic scales and visibility settings for both revisions.

* Check each wrist in an oblique view that shows the cuff opening and palm.
  Compare transverse sections through each arm and sleeve. Shift the sleeve
  centerline to follow shoulder, elbow and wrist, tapering edits toward the
  collar and hem. Adjust cuff length separately to match the exposed hand.
* Compare the rear clothing surface with the body's back at the same height
  and lateral position. Localize any clearance offset to the failing panel.
  Recheck the shoulder beneath the hair and inspect long triangle faces as
  well as vertices. An interior vertex test alone can miss face crossings.
* For closed boots or socks, test each leg separately. Cast from foot samples below the opening toward toe, heel, both sides and sole against the matching shoe. Record the sampled region, direction, ray length and misses. Fit the sock shaft and shoe upper independently when they deform differently. Preserve the foot pose even when the input foot is pitched differently from the sole.
* For sandals or rigid platforms, place the sole under the corresponding fixed foot first. Cast plantar samples downward against the sole material or sole geometry, check forefoot and heel support, and measure the vertical gap. Then check strap–skin crossings and strap attachment to the platform in front, side and heel close-ups. Open sides are part of the shoe design.
* Inspect fixed-camera before/after views with the full body visible. Temporarily
  hide a long skirt in matching footwear close-ups when it obscures the heel.
  Record raw triangle-pair counts per affected mesh pair and limit acceptance
  claims to the pose and pairs checked.

### Choosing a local repair

| Observation | Repair and verification |
| --- | --- |
| The neck looks continuous from the front but opens under the chin or at the rear | Inspect the bare join first. On semantic splits the actual interface may follow the face and rear skull. Find the corresponding boundary on each supplied mesh and fit those loops before considering a new neck band. Use the mandatory eight-view neck check above. |
| The scalp is exposed, or coverage passes while the hairstyle looks too small or flares backwards | Fit the cap against crown and temples, then compare the fringe against the eyes and ears. Inspect the roots, widest point, direction of the curve and tips of long or paired locks in both profiles and from behind. Keep fitted roots anchored while adjusting the free lengths. Recheck ears, neck, shoulders and collar after each change. A cap designed to sit under an omitted hat may have a genuine opening. |
| Matched garment patterns look right from the front but the waist or shoulder floats in profile | Use the motifs to constrain frontal placement. Check depth on the fixed body in both profiles. Verify the intended overlap at the waist or align corresponding open rims where the two pieces share a seam. Inspect inner sleeve, outer shoulder and nearby hair together. |
| A hand crosses a sleeve or protrudes through a gauntlet | Establish the intended exposure of the fingers from the reference. Inspect the actual wrist aperture and any faces closing the cuff. Fit the outer garment around the fixed hand, checking the wrist connection, inner lining and original silhouette. Keep integrated gloves and boot linings inside their original garment object. Respect case-specific topology and UV locks. If a capped aperture requires a permitted topology change, work on a copy, retain materials, interpolate UVs locally and disclose the edit. |

Prefer a whole-part pose correction for global misplacement. For a localized failure, move the affected vertices with a smooth transition into neighboring geometry. Reopen the revision and check every interface touched by the edit. Roll back a change that clears a crossing by detaching a layer, swelling a shoe or distorting a lock.

### Static review acceptance

Record separate findings for geometric contact, reference alignment and user approval.

- **Geometry.** Reopen the saved scene. Verify the protected body and foot pose, face shape outside the authorized interface, packed textures, and any required topology and UV invariants. Report raw triangle-pair intersections. Match contacts at intentional seams to the actual shared edges or vertices and test for crossings away from them. Report coverage and gap for the relevant surface as well as intersections.
- **Reference alignment.** Show the reference alongside the complete unmasked character before and after from front, both sides and back. Lock camera, scale and lighting between revisions. Add the bare neck and the specific interfaces at issue. Check fringe, ear exposure, swept or paired hair, garment length, cuffs and shoe support at a readable scale. Keep a zero-intersection scene with a visibly mismatched silhouette in review and continue from the last visually sound revision.
- **Blind scoring.** When an original layout is available for scoring, record the candidate digest before opening it. For each part report the 95th percentile and maximum bidirectional nearest-vertex distances as percentages of fixed-body height. Read these alongside the silhouette and contact evidence. A later fit informed by those scores is a separate, score-informed revision. Record explicit user visual approval separately from a passed static check.
