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
| Diagnose and repair | Select the earliest shared cause. If the cause is unclear, run the local diagnostic below once with the failing view, target and suspected neighbors. Compare the full view, temporarily hidden occluders and isolated target. For an exposed panel, sample rays in the intended covered region to distinguish missing coverage from a crossing. | For repeated coverage trials at one interface, use [fast candidate review](#fast-candidate-review) to measure and locate the visible patch. Change one cause per experiment. Batch independent, already diagnosed edits on a copy when their contact neighborhoods are disjoint. If a correction creates a new defect, return to the last sound revision. |
| Re-review | Reuse the original reference, baseline renders, and input analysis for identical assets. During local iterations render the failing views and the views that expose affected neighbors. Run the full four-view and interface review on the selected candidate; revisit an accepted region when the edit affects its geometry, visibility, pose or attachment. Carry forward explicit user acceptance of design details. | If the same defect recurs, record what the previous experiment ruled out and change the measurement, cause or repair. Continue on the saved scene until both local geometry and appearance pass. |
| Handoff | Reopen the selected scene and run the full acceptance checks below, including the neck views where applicable. Deliver the exact candidate and its review sheet in Studio when invoked there. | Record user approval on that version. A rejection reopens Assemble at that candidate with the user's feedback. |

For the initial analysis and for replaced inputs, run from the skill directory:

```sh
blender -b --factory-startup --python-exit-code 1 -P scripts/inspect_parts.py -- CASE_CACHE PARTS/*.glb
```

The final `ASSEMBLE_INTAKE` JSON log line maps each input to its bounds and four axis-labelled RGB views. Identify the actual front visually. The cache uses the embedded GLB bytes, inspection script and Blender build. Reuse neutral previews across placement changes; a reference, camera or pose change still requires new placement evidence. External buffers or texture files must be packed into an analysis copy first.

At first placement compare the shoulder line, waist and hem with the complete A-pose before any contact edits. Register the front reference to the fixed figure with the sole line and a second stable body landmark. Record the landmarks used and mark hidden or unmarked heights as uncertain. For a seamless dress inspect waist width and taper at a corresponding body level. Check the hem in profile and from behind. Save the registered comparison and carry those heights into final review.

Fit each complete part with translation, rotation and one uniform scale. Keep coupled garments together and place each shoe as a whole. Compare shoulder, waist, hem, toe, heel and sole landmarks as applicable against the A-pose. Check both the outline and the apparent size: a uniformly enlarged shell can cover the body and still look oversized. Save the best reference-matched placement as the shape baseline. If coverage and proportions pass, freeze that part.

Only consider moving garment or footwear vertices when a specific penetration persists after checking whole-part placement at reference-compatible sizes. Record the failing view and the two contacting surfaces. Confine the smallest smooth correction to that patch, with surrounding geometry anchored. Compare the baseline and candidate in the same failing close-up, a second angle and the full four views. Preserve topology, UVs, outline, openings and construction details. Roll back any correction that introduces a noticeable bulge, flattening, stretch or crease. When coverage requires conspicuous distortion or an oversized part, retain the shape baseline and record the fit conflict.

At first placement, align each shoe cavity to its fixed foot using its sole plane, heel, toe and shaft. Measure each side independently even when both shells belong to one mesh. For a confirmed shaft penetration on disjoint standing boots, use the footwear helper only on the affected flexible region. Protect the sole, toe, heel and rigid trim. Fit the torso plate against chest depth and shoulder width, each gauntlet against its own fingers and wrist, and the head against the actual neck interface. Solve offsets for the relevant regions of a coupled garment while preserving the shared object, UVs and topology. Check visible coverage and the space between layers in profile. A head's neck seam and hairline require separate evidence.

Freeze the approved rigid placement before the first vertex edit. Keep its full-review geometry.json and source-surface NPZs with the case. For each planned contact edit define the flexible patch and its protected neighbors before trying variants. Compare the whole part, each edited patch and protected construction details against that same placement on every retry. Inspect an isolated matched-scale native profile or wireframe beside the dressed contact view. A visible silhouette change or a failed shape limit rejects the trial even when every crossing clears. Restore the last shape-preserving placement and change the fit hypothesis. Record an unresolved input conflict if the fixed pose, intended dimensions and coverage cannot be reconciled within those bounds.

At first review, put the complete four views and the suspect interfaces on one sheet. Inspect the whole dressed character in each view, including the back, even when the current experiment targets a single part. Apply the visible-breakthrough rule below before recording an overall result. Choose the face, garment and contact angles that can distinguish the current risks. Keep the renderer, lighting, scale and frame definitions for all subsequent rounds. Add an `overview` list to the camera plan, e.g. `["collar=left","cuff=back_right"]`, and a `full` frame. Run once from a Python environment with Pillow:

```sh
python scripts/review_sheet.py overview CANDIDATE.blend cameras.json FIRST_REVIEW --blender /path/to/blender
```

For the first reasoning pass and final review, prefer a grouped packet. In the same camera plan, set `review_reference` to the case reference image path (relative to the plan or absolute) and `review_groups` to an ordered list. Each group has a `title` and `views`, for example `[{"view":"wrist_left=front","check":"Thumb root, fingertips and cuff overlap"}]`. The overview command above renders the four unmasked whole views plus the distinct listed views in one Blender launch, audits the meshes, and writes the combined sheet, a native-resolution HTML index and a separate JPEG per group. Use the group sheets together when the combined image would be downsampled. Keep the simpler `overview` list available for existing plans.

Choose groups from the supplied parts, their construction and prior failure modes. Show the forehead/fringe and rear crown, the dressed collar and a bare neck profile, both sleeve roots and the back, waist/hem and any overlapping layers. For gloves or long sleeves, give each side its own framing from fingertip through wrist with an angle into the thumb root and cuff. For shoes or socks, frame both sides separately and include shaft, instep, heel and sole. Include a second direction that actually exposes the opening. Verify that the target fits inside the crop and the nearer hand, prop or opposite limb does not obscure it. Label diagnostic visibility changes. Add applicable accessories and asymmetries from the current case.

Place the unmasked crop next to its same-camera isolation when an apparent breakthrough could be trim or an intended opening. On the dressed tile set `compare_with` to the paired selector and `rgb_tolerance` to the case's 8-bit channel tolerance. The sheet outlines the changed extent; the HTML tile opens the untouched image. Treat that outline as a location to inspect. Read the reference, whole views, close-ups and available geometry measurements together. Record all observed failures, affected sides/views, likely shared causes and uncertainties before changing geometry. On an intermediate round carry this context forward and refresh the failed groups and adjacent interfaces. Reuse the full packet for final review.

Open `FIRST_REVIEW/overview.html` to inspect any tile at full resolution in one click, or use the portable `overview.jpg`. Each tile label is the exact `FRAME=VIEW` selector for focused re-review; inspect its original PNG at native resolution when needed. Reuse this command and camera plan on the final candidate to obtain a matched sheet.

For a repair history, first check the saved review directories for the failing view, its diagnostic counterpart and the preceding checkpoint. Compose matched native pixels and a fixed crop directly, including for rejected trials and rollbacks:

```sh
python scripts/review_trace.py trace-plan.json TRACE_OUTPUT --guard-frame
```

Example plan (paths relative to the plan, ROI in original pixels with exclusive right and bottom):

```json
{"rgb_tolerance":18,
 "states":{"initial":{"review":"initial","diagnostic":"initial-body-hidden"},
           "repair":{"review":"repair","diagnostic":"repair-body-hidden"}},
 "rows":[{"title":"Wrist opening","before":"initial","after":"repair","inner":"body",
          "view":"wrist=front","roi":[100,150,320,340],"note":"Check the thumb root against the cuff."}]}
```

Use the optional row field `interface` to give multiple views of the same physical opening one decision. Keep independent sides and layers separate. Open `decisions.md` first. Start with the indicated evidence rows, inspect all relevant neighbors, and review the reported full-frame bounds outside the crops. Increased visibility may be intentional at an opening. Unchanged visibility cannot establish correct placement or shape.

Record one repair decision per affected interface: the observation, suspected cause, smallest reversible edit and view that could disprove it. Batch edits on independent meshes. For edits sharing a mesh or contact surface, keep an intermediate checkpoint so each change can be rolled back. If the same patch persists, compare the opening and depth ordering before choosing another edit. Carry accepted interfaces forward and rerender the changed interface and its neighbors. Close with the full unmasked review. Measure elapsed time from the first evidence being ready to the reviewed repair decision, including diagnosis, edits, failed attempts and looking at images. Track machine time and the number of geometry revisions separately.

Choose the ROI and RGB tolerance from the current case. When both visibility states are in one review folder, omit `diagnostic` and set the row's `diagnostic_view` to the isolated frame selector. Keep the same lighting, material state, visibility and framing across comparisons except for the explicitly hidden inner layer. Verify legacy render settings from case provenance if missing in both reports. The image places the ROI in context, shows both native crops and colors newly visible, persistent and cleared pixels separately. Use this to tell a regression from a small net improvement that merely moved the exposed patch. Validate the cause against the original crops and any existing geometry checks. These are screen-space visibility measurements. Reuse stored images for magnification, different crops or a different threshold; render a new view only for missing evidence, occlusion, insufficient native detail or a changed candidate.

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

For each failed interface, record the visible defect, its likely cause and the one change being tested. Start from the last visually sound scene. Reuse accepted parts and settings. Preview the affected region from the failing view and a second angle, then recheck its immediate neighbors. If the edit does not improve the specific defect, discard it and revisit the diagnosis before attempting another edit. When an in-scope upstream revision is needed, carry the failing views, measured clearance, approved dimensions and locked interfaces into a copy of the affected component. Execute the component revision and return it to the same saved-scene review within the current run. Keep the original fit baseline across retries and identify any change to the component pattern explicitly. A rejected trial, exhausted local vertex budget or stage transition is an intermediate result. Continue with the next distinct supported repair while preserving the user's limits. Pause only for a concrete dependency or a scope decision that blocks the remaining repairs, and identify the missing asset, permission or incompatible constraints. Keep diagnostic images separate from the candidate sent to Studio for acceptance. Once local checks pass, run the full saved-scene geometry and visual checks for delivery.

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

Start from a saved baseline. Select the first failing interface, measure its coverage and inspect same-camera images. Review the saved whole-part placement and the residual penetration against the shape baseline before enabling vertex edits. Derive garment placements and hair length from the current case's full reference views and protected meshes. Keep original layouts isolated until scoring in a blind run.

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

### Hair placement and review

Set `hair_frame` around the fixed head. Register the cap using the crown, brow and temples. Long locks and asymmetric ornaments can shift the center of the whole-hair bounding box. Start each revision from the latest accepted placement. If a prior edit flattened the hair, recover its last shape-preserving mesh at the approved scale.

- **Depth.** Compare the fringe-to-forehead gap, side locks against the nose and chin, and ear exposure in both profiles and a three-quarter view. For a forward or backward placement error, translate hair and attached ornaments together along the head's front axis. Preserve the cap's front-to-back thickness.
- **Height.** Hold the selected depth and rotation fixed. Compare small vertical translations in the same front and profile frames. Read the crown and lower fringe against the brow, upper eyelid and intended eye visibility in the reference. Choose the smallest shift that corrects the silhouette. Scale trial offsets to this head and its available clearance.
- **Local contact.** Once placement is sound, anchor the roots and swing a colliding free lock around its attachment. Preserve its length, curl and ornament position relative to the strand. Limit residual vertex edits to the interfering fringe or tip and its transition. Compare cap depth in matched orientation and corresponding strand edges against the shape-preserving mesh.
- **Re-review.** Inspect the unmasked whole character from four sides and matched head close-ups. Sample scalp coverage around the crown, temples and rear. Check fringe–head and tip–clothing intersections separately and record residual whole-head contacts. With a front-only design reference, use side and rear views to verify physical fit. Continue on failed regions until shape, placement and contact checks pass together.

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
* Freeze the intended cuff design before correcting contact. Record the rim's high and low points relative to the wrist, opening width, visible wrist length, and any continuous decorative band. Use the character's own reference and source garment. For blind tests keep the accepted assembly sealed until scoring. An approved example from another character can guide the review angles.
* Inspect each cuff looking into the opening and across the sleeve wall. Compare the dressed view with the hand temporarily hidden to locate a recessed cap. Register the sleeve centerline to the fixed forearm using placement and pivot adjustments first. If an authorized opening repair is needed, retain the visible outer rim, its slope or drape, trim and intended hand exposure. A straight recut that removes a hanging corner or exposes extra wrist fails even with zero contact pairs.
* Report coverage and shape together for each edited side. Measure edge change on each sleeve root against the frozen placement, inspect the largest changes on the mesh, and compare shoulder and cuff outlines in matched front and shaded oblique views. Check a new panel's joins and silhouette around the exported model. Reject a localized bulge, spike, flattened trim or hand exiting a sidewall even when whole-garment percentiles and covered-pixel checks pass.
* Compare the rear clothing surface with the body's back at the same height
  and lateral position. Localize any clearance offset to the failing panel.
  Recheck the shoulder beneath the hair and inspect long triangle faces as
  well as vertices. An interior vertex test alone can miss face crossings.
* For closed boots or socks, test each leg separately. Cast from foot samples below the opening toward toe, heel, both sides and sole against the matching shoe. Record the sampled region, direction, ray length and misses. Fit the sock shaft and shoe upper independently when they deform differently. Preserve the foot pose even when the input foot is pitched differently from the sole.
* When footwear looks elongated, measure the original material edges separately on each side in the toe-to-heel region and shaft after removing the agreed uniform scale. Compare the 95th percentile and worst edge-length ratios, the toe-to-heel silhouette in profile and the complete footprint including any infill. If a shaft correction is required after whole-shoe fitting, distribute it with length-preserving deformation. Verify any added coverage panels separately from the original-edge statistics. Use the reopened scene and identical foot close-ups before handoff.
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
- **Preserve garment dimensions during rework.** Save the source garment at its reference-approved uniform scale. Measure width, depth and height in the same garment-aligned axes, and keep landmarks for the straps, hems, waistband and leg openings. For adjacent garments include the visible gap between them. Try rigid placement first. After a repair compare the complete garment including lining to that baseline, and check corresponding source edge lengths and the four silhouettes. Keep infill inside the intended garment boundaries. Reject a fix that broadens the silhouette, lengthens a garment or fills intended exposed skin. Record any remaining fit conflict for review when the locked dimensions preclude further coverage.
- **Visible breakthrough fails the complete assembly.** At first and final review, mark the candidate failed if any unmasked full view or required close-up clearly shows skin or an inner layer breaking through an area the outer garment should cover. A contrasting patch across the back or a narrow strip at a sleeve root can both qualify. Record the failing view and interface even when the component under test passes its own checks. If the region could be trim, a garment opening or an exposed area in the design, compare the reference and a same-camera diagnostic render with the suspected inner layer temporarily hidden. Repair the confirmed interface on the saved scene, restore all layers and inspect the failing view, neighboring angles and complete four views again before handoff.
- **Minor garment intersections.** Accept a localized overlap when the full views and the relevant close-ups retain the intended coverage, silhouette, attachment and layer order. Record the affected parts and views. A visible inner sleeve breaking through the outer shoulder, a hand exiting through the sleeve wall, or a sole losing support requires repair. Raw triangle-pair counts are diagnostic and have no universal cutoff. Apply the separate neck-interface checks to the head/body join.
- **Blind scoring.** When an original layout is available for scoring, record the candidate digest before opening it. For each part report the 95th percentile and maximum bidirectional nearest-vertex distances as percentages of fixed-body height. Read these alongside the silhouette and contact evidence. A later fit informed by those scores is a separate, score-informed revision. Record explicit user visual approval separately from a passed static check.

### Fast candidate review

At first review, frame both sides of each suspect interface tightly enough to distinguish the opening from the adjacent shell. Save the failing view, its covered pixel region and a shape-preserving checkpoint. Compare that checkpoint and one cause-specific repair first. If the same exposed patch persists in the same place, inspect the original opening and the direction of the gap before generating another variant. Batch already available alternatives for this interface in one Blender process:

```sh
blender -b --python-exit-code 1 -P scripts/screen_variants.py -- cameras.json SCREEN checkpoint.blend trial.blend
```

Add an ordered `screen` array to the review plan. Each probe specifies `frame`, `view`, the `inner` mesh to temporarily hide, an optional upper-left pixel rectangle `roi: [left, top, right, bottom]` (exclusive right/bottom), `rgb_tolerance` in 8-bit channel units and `max_pixels`. Use matched flat textured renders and a region the reference shows should be covered. Exclude intended skin openings, silhouettes with legitimate visibility changes and unrelated anatomy. Derive tolerances from same-camera evidence for this case. If coverage is ambiguous, use the regular focused visual review. Put the most diagnostic failing view first, followed by a neighbor that can reveal regression.

The screen checks configured geometry limits first, then compares dressed and isolated images. Open `overview.html` for the dressed and diagnostic views with the affected bounds highlighted; click either image for its native resolution. A failed probe skips the remaining probes for that candidate. Its row in `screen.json` gives the affected pixel count and bounding box in the saved image. Set the optional mesh name `outer` to back-project sampled failing pixels onto the inner surface and find the nearest outer triangles in world space. Use those triangles and the ray depths to inspect the shell or rim directly on the next attempt. Inspect the original pair at that location. A surviving candidate still needs the complete unmasked four-view, local shape and interface checks. Record fitting/decision time separately from screen execution time.

For residual shaft penetration in standing footwear, `scripts/footwear.py:fit_pair` can supply a candidate after whole-shoe fitting. Apply only the affected flexible patch and verify the protected regions against the saved baseline. Each side samples only triangles that cross its section height. The sides are fitted independently. Serial execution is the default. Benchmark `parallel=True` on the target mesh and machine before enabling two workers. Check each shell's identity and the body-aligned axes first.

For bounded vertex repairs, put `geometry_limits` in the shared review camera plan before running the overview or focused views. Map each region name to its Blender mesh `part`, a plan-relative `reference` NPZ and one or more measured limits: `max_displacement` in scene units, `min_edge_ratio`, `max_edge_ratio`, `max_p95_edge_ratio` (candidate length divided by source length), or `max_p95_abs_relative_change` (95th percentile of the absolute fractional length change, counting compression and stretch). Save the fixed source in the intended rigid placement and uniform scale with world vertices `p`, triangle indices `t`, and optionally a one-dimensional array of original vertex indices `ids`. Use corresponding vertex IDs and retained edges; define separate budgets for rigid and flexible regions from the current input and approved fit. Inspect newly added lining and the complete garment silhouette in the visual review.

A failed preflight writes the measurements to `preflight.json` and stops that candidate before image rendering. Repair the named region and rerun into a fresh review directory. A passing candidate continues through the same-camera contact and visual checks.


### Shape evidence for Studio handoff

Use `--handoff` on the final `review_views.py` or `review_sheet.py overview` command. Ordinary packets are diagnostic. Set `handoff_baseline` in the camera plan to the frozen rigid-placement geometry.json. For every changed part, supply `geometry_limits` with both `max_extent_change` and `max_p95_abs_relative_change` for the entire original part and each edited or protected region. Store full baseline world vertices and triangles in each reference NPZ and select local regions with `ids`. Extent change is the largest fractional change in the three baseline-aligned world-axis spans. Retain a displacement limit for protected locations and inspect oblique features in their own axes. Render the rigid baseline with these same region specifications and case tolerances before repair. Retain the NPZs unchanged. Review a new rigid placement against the reference before freezing it; carry the original shape forward when changing placement.

A handoff packet must record `shape_review: verified_for_visual_review` and pass the same-camera visual comparison before labeling the case ready in Studio. Missing vertex correspondence following an authorized seam or topology edit requires an explicit mapping or a separate protected-surface measurement and visual review; do not substitute a newly edited mesh as its own reference. Retain failed images for diagnosis and keep them labeled as failed.
