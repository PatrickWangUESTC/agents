---
name: assemble
description: Assemble textured character parts in Blender from Component Gen or independently normalized meshes. Use for static fitting to four-view references, head/body seams, hair silhouettes, layered clothing and footwear contact.
---

## Inputs and blind trials

Start when the complete A-pose, part identities and each selected textured GLB are available. Component Gen is the local upstream skill. Use its final texture_model receipt or its paired GLB, including delight=true outputs. Match the receipt to its part and preserve its geometry, UV and base color. Resolve relative model paths using the generating workspace; pass a resolved GLB directly when moving a case. For timing, start a monotonic clock at assembly intake and stop after fresh-scene and visual review. Record reused case-specific placements and executor time separately.

For a blind trial, use the complete character reference, the fixed body and the independently centered and scaled parts in the agreed inventory. Inspect front and profile RGB renders of each textured input. Their independent framing removes the relative scale. Determine whether the body contains a continuous torso, arms, legs and feet, or only the skin exposed by the original outfit. Record which interfaces the supplied geometry can test. Keep coupled garments together. If a reference hat, belt or lining is absent, record its effect on the visible outline and evaluate the supplied pieces within the agreed scope.

Use visible landmarks on the fixed body to calibrate scale and the foot baseline. The original front image can supply fingertip positions or garment motifs. Verify both profiles for depth and the back for layer order. Check that low-contrast boots or gloves survived reference cropping by comparing with the uncropped turnaround. Keep original transforms, source assemblies and original per-part projections outside fitting. Label a resumed blind checkpoint as a resumed trial.

## Execution from a new case through user review

Use the case work directory for evidence and timings. The clock starts before the first input inspection. For each analysis, fit, render, review and rework round, record the start, finish, candidate, observed defect, decision and next action in the case notes. Mark tool runtime, active agent analysis and time awaiting user input separately. On a new case, derive all placements from the supplied inputs. A replay with saved placements measures executor speed only.

| Stage | Work to batch or reuse | Condition for continuing |
|---|---|---|
| First inspection | In one Blender launch inspect all supplied GLBs with the command below. Read the complete reference and the part previews together. Record front axis, foot baseline, intended coverage, fixed geometry, coupled pieces and available neck rims. | One placement plan explains relative height, orientation and layer order. Resolve input or axis mistakes here. |
| First placement | Fit the fixed body and rigidly place the parts. Save one unmasked baseline and camera setup. Review the whole four-view sheet in one pass. Collect all defects, their failing views and affected interfaces before choosing a repair. | A shared pose, scale or orientation error goes back to placement. Local failures go to the saved baseline. |
| Diagnose and repair | Select the earliest shared cause. If the cause is unclear, run the local diagnostic below once with the failing view, target and suspected neighbors. Compare the full view, temporarily hidden occluders and isolated target. For an exposed panel, sample rays in the intended covered region to distinguish missing coverage from a crossing. | Change one cause per experiment. Batch independent, already diagnosed edits on a copy when their contact neighborhoods are disjoint. If a correction creates a new defect, return to the last sound revision. |
| Re-review | Reuse the original reference, baseline renders, and input analysis for identical assets. During local iterations render the failing views and the views that expose affected neighbors. Run the full four-view and interface review on the selected candidate; revisit an accepted region when the edit affects its geometry, visibility, pose or attachment. Carry forward explicit user acceptance of design details. | If the same defect recurs, record what the previous experiment ruled out and change the measurement, cause or repair. Continue on the saved scene until both local geometry and appearance pass. |
| Handoff | Reopen the selected scene and run the full acceptance checks below, including the neck views where applicable. Deliver the exact candidate and its review sheet in Studio when invoked there. | Record user approval on that version. A rejection reopens Assemble at that candidate with the user's feedback. |

For the initial analysis and for replaced inputs, run from the skill directory:

```sh
blender -b --factory-startup --python-exit-code 1 -P scripts/inspect_parts.py -- CASE_CACHE PARTS/*.glb
```

The final `ASSEMBLE_INTAKE` JSON log line maps each input to its bounds and four axis-labelled RGB views. Identify the actual front visually. The cache uses the embedded GLB bytes, inspection script and Blender build. Reuse neutral previews across placement changes; a reference, camera or pose change still requires new placement evidence. External buffers or texture files must be packed into an analysis copy first.

At first placement compare the shoulder line, waist and hem with the complete A-pose before any contact edits. Register the front reference to the fixed figure with the sole line and a second stable body landmark. Record the landmarks used and mark hidden or unmarked heights as uncertain. For a seamless dress inspect waist width and taper at a corresponding body level. Check the hem in profile and from behind. Save the registered comparison and carry those heights into final review.

Prefer the smallest change that restores the reference silhouette and coverage. Start with rigid placement. When inputs were normalized independently, establish uniform scale from this case before local fitting. Keep an already aligned part in place. Use the supplied pose, proportions and part construction to choose landmarks and correction bounds for each run.

At first placement, align each shoe cavity to its fixed foot using its sole plane, heel, toe and shaft. Separate the left/right connected shells for measurement even when both are in one mesh. For a standing pair with disjoint lateral halves, use `scripts/footwear.py` (`fit_pair`) on body-aligned world vertices and triangles after placing the soles. Measure the ankle and occupied shaft levels on this character. The helper preserves the lower shoe as a rigid group and adjusts the shaft above the ankle. Skip shaft fitting for low shoes. For rigid armor or a decorative rim crossing ankle height, protect the whole rigid piece and fit only the flexible region. Compare the profile and local edge lengths against the uniformly placed source before keeping a correction. Fit the torso plate against chest depth and shoulder width, each gauntlet against its own fingers and wrist, and the head against the actual neck interface. Solve offsets for the relevant regions of a coupled garment while preserving the shared object, UVs and topology. Check visible coverage and the space between layers in profile. A head's neck seam and hairline require separate evidence.

At first review, put the complete four views and the suspect interfaces on one sheet. Choose the face, garment and contact angles that can distinguish the current risks. Keep the renderer, lighting, scale and frame definitions for all subsequent rounds. Add an `overview` list to the camera plan, e.g. `["collar=left","cuff=back_right"]`, and a `full` frame. Run once from a Python environment with Pillow:

```sh
python scripts/review_sheet.py overview CANDIDATE.blend cameras.json FIRST_REVIEW --blender /path/to/blender
```

Open `FIRST_REVIEW/overview.html` to inspect any tile at full resolution in one click, or use the portable `overview.jpg`. Each tile label is the exact `FRAME=VIEW` selector for focused re-review; inspect its original PNG at native resolution when needed. Reuse this command and camera plan on the final candidate to obtain a matched sheet.

To render the complete plan without composing a sheet:

```sh
blender -b CANDIDATE.blend --python-exit-code 1 -P scripts/review_views.py -- cameras.json NEW_REVIEW_DIR
```

The camera JSON takes a horizontal `front` vector and a `frames` object. Each named frame supplies a world-space `center` and positive orthographic `scale`. Include the whole figure and each applicable interface, including both hands and both feet. For the bare neck, add `"diagonals": true` and a `hide` array listing its occluders. Reuse the identical plan across revisions. The report audits all unmasked meshes before rendering and records the views. Inspect the images before freezing. Time continuously from intake through this visual decision, including diagnosis, script edits and failed trials. Record offline scoring and publishing separately.

For local iterations keep the original camera plan and pass only the named frame/direction pairs needed to judge the defect and its neighbors. For example, if the plan contains these frames:

```sh
blender -b REVISION.blend --python-exit-code 1 -P scripts/review_views.py -- cameras.json ROUND_DIR --focus sleeve_wall=back wrist=front_left
```

Each focused run computes all configured contact boxes in the selected frames once and renders the named directions at the original resolution. The report labels the run as a local iteration. Carry the intake analysis, placements, before images and prior observations forward. Change only the failing region; when using the clearance solver, set the step’s `vertex_group` to a measured garment repair group with a weighted transition at its border. The solver visits triangles incident to movable vertices and keeps vertices outside the group fixed. Use separate steps for different group names. Keep a shared placement or pose error in the full review loop. If a local trial stalls or the edit affects coverage beyond its intended boundary, inspect the adjacent interface and revise the diagnosis. Once the local defect clears, reopen the chosen revision and run the complete camera plan without `--focus` before handoff.

For an ambiguous local failure, run:

```sh
blender -b --factory-startup --python-exit-code 1 -P scripts/inspect_fit.py -- REVISION.blend DIAG_DIR --before BASELINE.blend --part TARGET --neighbor BODY --occluder ACCESSORY --front X Y --view back
```

Use actual object names and the case camera direction. Repeat `--neighbor` or `--occluder` as needed; omit the occluder when none is suspected. For a first diagnosis omit `--before`. One call saves matched crops and raw triangle-pair counts for the named neighbors. Restore all parts for final visual acceptance. A suspected missing panel that remains exposed with the accessory hidden requires a panel coverage check; a defect visible only with the accessory shown requires an attachment and depth check.

## Assembly loop

Use the complete character's four-view A-pose as the default assembly reference: front, one profile, back and the opposite profile. When only a front image is available, retain it and generate the turnaround from it. Record view order and provenance, check the pose, common scale and foot baseline, and use all four views during placement. In blind evaluation, reserve the original assembled geometry and its side and back renders for scoring after the candidate is frozen.

1. Inspect the complete A-pose, the individual parts and the actual imported axes. Identify the front, feet, shoulders, cuffs, hem, chin and hairline. Write a case JSON as described below. Use source coordinates of the fixed body as assembly space.
2. Run a baseline with only translations, rotations and uniform scales. Compare front, both sides and back. Inspect face readability, scalp exposure, wrists at cuffs, exposed thighs, boots, layer order and accessories. Inspect each side independently. For a pair of separately connected shoes needing distinct motion, move each whole connected shoe rigidly in a derived part file and record its transform. Keep the original asset.
3. For separate head and body meshes, apply the [mandatory neck acceptance checks](#mandatory-neck-acceptance) before handoff. The bundled neck fitter supports a star-shaped head perimeter and a closed upward-facing body cap. Adapt the local fit to the measured perimeter for other topologies.
4. Diagnose intersections on the full geometry with the complete body visible. For failed coverage or visible crossings, run the contact refinement loop. Save revisions separately and compare against the same baseline.
5. Apply the [static review acceptance criteria](#static-review-acceptance). Deliver the selected editable project, packed textures, four full views and interface close-ups after the applicable checks pass. Keep the source assets and case configuration for reruns.

### Reducing repeated fits

Save the rigid placement and its camera frames once. Before a detailed seam fit, compare the unmasked full front and profile with the reference: check head size and tilt, shoulder and waist height, foot baseline and the dominant clothing and hair silhouettes. Correct a shared scale or orientation error at placement before spending time on individual contacts.

For each failed interface, record the visible defect, its likely cause and the one change being tested. Start from the last visually sound scene. Reuse accepted parts and settings. Preview the affected region from the failing view and a second angle, then recheck its immediate neighbors. If the edit does not improve the specific defect, discard it and revisit the diagnosis before attempting another edit. An upstream reference or mesh mismatch returns to the earliest affected stage with the specific part and evidence. Once local checks pass, run the full saved-scene geometry and visual checks for delivery.

Record elapsed time for placement, local solves and final verification separately from time awaiting visual review. Use the per-step `history`, `applied_pairs`, `max_offset` and `seconds` in the contact report to choose the next edit. Compare actual applied pairs after the height fade with the initial count. If counts stall at the displacement limit, inspect a section or coverage sample before widening the edit. For a glove that means fingertip enclosure and cuff continuity; for socks and shoes, inspect shaft and sole separately. If counts drop while the reference silhouette worsens, restore the prior fit and change the local constraint. A shared boundary can have intentional contacts.

### Four-view re-review and recurring failures

At each re-review present one contact sheet with columns front, left, back and right and rows for the reference, baseline and selected candidate. Freeze one camera frame, scale, light and visibility configuration for both render rows. Keep the full body visible. Use `python scripts/review_sheet.py BEFORE AFTER sheet.png --references FRONT LEFT BACK RIGHT` with Pillow and the four correctly ordered reference panels. Preserve proportions. Label generated turnaround references and report any missing accessory or incomplete body region. Open the sheet before selecting the revision. Add close-ups where the four full views lack resolution.

| Repeated failure | Earliest discriminating view and next check |
|---|---|
| The face looks different after a seemingly good neck fit | Compare front and both profiles with the source head at equal eye spacing. Inspect the bare face and then hair and collar together. Localize the first change before editing. |
| Hair matches the back outline while the forehead or scalp remains bare | Read fringe height against the eyes in front, crown coverage in profile and locks from behind. Check cap coverage and head–hair crossings separately. |
| Gloves or shoes lose their silhouette while crossing counts fall | Check front for width and both profiles for fingertip or toe protrusion, then inspect cuff or heel close-ups. Keep original shells, topology and UVs when required. |
| A collar, sleeve or skirt looks plausible from the front and clips in depth | Inspect the back and each profile, then sample the failing cross-section on the fixed body. Distinguish an incomplete body from a detached garment and record which contact checks its mesh supports. |

## Contact refinement loop

Start from a saved baseline. Select the first failing interface, measure its coverage and inspect same-camera images. Fix gross placement with uniform scale and translation before moving local vertices. Derive garment placements and hair length from the current case's full reference views and protected meshes. Keep original layouts isolated until scoring in a blind run.

Run the contact solver on single-mesh static parts in Blender world space (+Z up, facing -Y). Supply a fresh output directory.

```sh
blender -b BASELINE.blend --python-exit-code 1 -P scripts/refine_contacts.py -- contacts.json NEW_OUTPUT
```

The configuration names the protected `body` and `head`. Optional `scalp` names the `hair` object, its cap material slots (`cap_materials`), and `reference_height_ratio` measured as crown-to-tip hair height divided by head-top-to-sole figure height. Inspect the material selection first: the cap surface should cover the crown, temples and rear; exclude trailing locks from cap measurements. The whole hairstyle moves together. Optional `placements` maps garment names to target world-space `center` and `height`. Each `clearance` step specifies a fixed `collider`, target `parts`, a clearance distance and maximum offset in fractions of collider height (`clearance`, `max_offset`), and `iterations`. Optional `height_fade: [low, high]` blends the correction from zero to full strength between those relative collider heights, e.g. to protect the fringe and ear silhouette. The solver writes a separate editable scene, reopens it and checks protected world vertices, topology, UVs and unmasked pair counts.

For a clearance repair the solver ranks proposals by intersections on the applied surface, including any height fade, then by squared displacement. The saved baseline participates in selection. On writing vertices, the solver checks the actual target–collider pair and previously clear neighboring mesh pairs. A full displacement that crosses a clear neighbor is retried at reduced fractions; when no tested move improves the target safely the step restores its input vertices. Read `applied_fraction` and `rejected_trials` alongside `applied_pairs`. With zero applied movement and a visible defect, revisit placement, coverage, or the occluding part before running another solve. Check already-intersecting neighbors, self-intersections, attachment gaps and the reference silhouette separately in the final review.

Recheck independently on the reopened candidate. Sample additional crown, side and rear rays between fit directions; report coverage, gap and uncovered locations. Inspect the eyes, temples, ears, cap silhouette and full strand lengths. Check the toe, heel, both sides and sole of each foot, and check the sleeve, torso, waist and skirt from multiple angles. A fall in pair counts can also mean two parts have detached. Compare the same mesh pairs before and after, identify residual contacts, and return to the last visually sound candidate when a local repair damages the design. Record the frozen revision before opening scoring data.

## Mandatory neck acceptance

For every separately assembled head and body, keep the assembly in review until both the geometry and the eight-view visual inspection pass.

- Judge the whole face against the approved reference. Compare the isolated head with the reference at intake, then render the placed head immediately before and after fitting with identical front and three-quarter cameras, lighting and expression. Compare the facial outline, cheek fullness, eye shape and spacing, nose and mouth placement, and the overall expression together. For image-to-render comparisons match head angle and apparent scale with uniform resizing. Record occlusions or perspective differences that limit the comparison.
- Keep local seam edits on the neck. Review the complete character with hair and collar visible as well as the bare face: head tilt, scale, fringe and collar can change how the face reads with unchanged facial vertices. If the overall face looks noticeably different, keep the candidate in review, identify the first divergent stage and correct that stage. Minor image-to-render differences are acceptable when the character retains the same likeness.
- If the neck appears long or short, compare chin, shoulder line and collar heights against the registered reference in front and profile. Correct the displaced part first. Keep an aligned head and seam in place when only the collar has drifted. If an attachment moves, repeat the seam and face checks.
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

* On feedback about a visible breakthrough, resume from the exact reviewed scene and camera plan. Add a separate close-up for each affected side, including a front or rear oblique that exposes the sleeve wall. Register the intended skin exposure and cuff position from this case’s reference. Keep covered upper-arm or forearm regions separate from the open cuff. In each relevant camera frame add `"contact": {"fixed": "<body mesh>", "garment": "<outer layer>", "bounds": [[xmin,ymin,zmin],[xmax,ymax,zmax]]}` with world-space corners measured on the fixed body. Reuse the boxes across revisions. The review reports unique triangle pairs inside each box and saves the matching views. Inspect the full sleeve as well as the sampled boxes. Record the side, view, visible skin and whether the arm exits through the intended opening. A visible breakthrough keeps the candidate in Assemble even with a lower whole-garment count. Correct the failed sleeve on a copy, then rerun the same review and check its neighbors. A zero count still needs a visual coverage check for an open or detached sleeve.
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

A failed visual or geometric check returns the affected interface to repair in the same run. Resume the reviewed checkpoint, preserve accepted parts, and execute a local correction. Reopen it and repeat the same-camera checks of the interface and its neighbors. If a trial distorts the silhouette, discard that trial and try a different local correction. A failure report is an intermediate result. Hand off the repaired candidate for user review after the checks pass, or identify the concrete missing input or constraint that prevents further repair.

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
- **Garment height and local shape.** Recheck the first-placement shoulder, waist and hem against the same reference framing. Compare each edited region to the native garment at matched scale and orientation. Inspect sleeve openings, hard panels, trims, shafts and soles in close-up. For a suspect area use wireframes or compare corresponding edge lengths after removing rigid placement and intended uniform scale. Reject a visibly shifted garment, pinched cuff, swollen shoe or distorted trim even if its collision count falls.
- **Minor garment intersections.** Accept a localized overlap when the full views and the relevant close-ups retain the intended coverage, silhouette, attachment and layer order. Record the affected parts and views. A visible inner sleeve breaking through the outer shoulder, a hand exiting through the sleeve wall, or a sole losing support requires repair. Raw triangle-pair counts are diagnostic and have no universal cutoff. Apply the separate neck-interface checks to the head/body join.
- **Blind scoring.** When an original layout is available for scoring, record the candidate digest before opening it. For each part report the 95th percentile and maximum bidirectional nearest-vertex distances as percentages of fixed-body height. Read these alongside the silhouette and contact evidence. A later fit informed by those scores is a separate, score-informed revision. Record explicit user visual approval separately from a passed static check.
