---
name: character-part-extraction
description: Prepare a reviewed front A-pose and use GPT-6 Astra with ImageGen to extract anime character parts for downstream mesh generation. Use for A-pose normalization, 2D 拆件, or preparing an asset atlas and individual part PNGs.
---

## Front A-pose

Inspect the supplied image. Generate a clean, straight-on, full-body A-pose when one is missing. Preserve identity, body proportions, hair silhouette, colors, costume layers and footwear. Keep hands away from the torso and both feet on the ground line. Place independent handheld props beside the character with clear space. Save and inspect the full-resolution A-pose for clipping and identity drift.

## Astra 2D extraction

Run 2D extraction with GPT-6 Astra and its ImageGen image-editing tool. Use the accepted A-pose as the image reference for the atlas and every correction. Use Tripo for downstream mesh, UV and texture tasks. In Pi Studio, if Astra with ImageGen is unavailable, save the A-pose checkpoint and ask for the reviewed Astra part PNGs to be uploaded to the same task. Continue from those parts after confirming they match the saved A-pose.

1. Decide part ownership from the actual outfit. Include the full neck and ears in the bald head-neck image. End the headless body at the base-of-neck seam, match skin and proportions to the A-pose, and use simple opaque base garments where coverage is needed. Keep mutually occluding costume layers together when they define one silhouette. Preserve continuous dresses and keep sleeves, lapels and trim with their garment. Group paired footwear and matching legwear as appropriate. Assign ornaments and independent props to the parts they belong to.
2. Ask Astra to produce a front-view atlas with one complete asset per cell. Specify the ordered semantic names, grid, background and gutters. A 3 × 2 layout works for five or six parts, with an empty last cell for five. Use a different grid or multiple sheets for larger sets. Preserve the accepted A-pose for scale and placement.
3. Inspect the actual cell boundaries before slicing the atlas into independently named PNGs. Preserve the original atlas and retain only the reviewed part version for modeling. Check the bald head and neck boundary, body proportions, garment ownership, paired footwear, missing or duplicate items, color and clipping. In occluded hair areas, reconstruct the inner strands and back-hair volume from visible cues and inspect the rear view when needed. Use the same A-pose to regenerate an individual part when its first version fails review. Record inferred hidden details.
4. Save the A-pose, atlas and one full-resolution PNG per part. Record source and A-pose hashes, the generation tool, ordered part names, file paths, ownership and review status. Show the A-pose and parts before advancing when the user requests a review. Pass the selected individual PNG for each part to component-gen.
