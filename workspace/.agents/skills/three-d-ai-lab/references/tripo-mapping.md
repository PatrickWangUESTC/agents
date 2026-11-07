# Public workflow mapping

Checked 2026-11-07 against:
- https://www.tripo3d.ai/tutorials/agentic-canvas-game-character
- https://www.tripo3d.ai/blog/gpt-6-astra-3d-character-workflow
- https://www.tripo3d.ai/tutorials/tripo-gpt-astra-bat-workflow

The Canvas tutorial exposes a prompt-driven AI 3D Lab/Astra node. A separate
character tutorial uses Astra with Blender MCP. These describe a workflow, not
the private Canvas implementation. The bat example separates asset generation
from subsequent Blender production. Do not infer proprietary code or model weights.

| Public concept | Local implementation |
| --- | --- |
| Models + reference + task | case JSON and case workflow |
| Astra interprets and edits | calling agent reads images and writes Blender Python |
| Blender connection | isolated headless Blender processes, not installed live MCP |
| inspect / assemble / repair | baseline inventory and case-specific operation scripts |
| results and follow-up requests | revision folders, renders, diagnosis, review |
| preserve unaffected work | immutable checkpoints, explicit property guards |
| iterate locally | run from selected checkpoint; keep failed branches |

The execution tools support general Blender operations; that does not prove a
general automatic repair or rigging algorithm. Existing character-assembly helpers
remain available; purple-hair fitting rules remain specific to that case.
The new Lab adds a reusable reasoning/execution/review boundary around operations.

Recipes must differ by case: already-generated meshes start at inspection;
existing rigged assets retain their rig; a static prop needs no skeleton.
Preserve the new case's requested split, reference skeleton, pose and delivery scope.
Do not silently impose a tutorial's body/head/hair split or replace existing meshes.
Hair palette, garment coordinates and skeleton templates belong to case inputs.

The character tutorial's steps 7-8 follow Lab refinement with optional head reference
extraction/generation/replacement, then Rigging and skeleton FBX export for engine use.
Our post-Lab continuation adds independent assembly, pose and fresh-process roundtrip
gates. Use character-canvas's from-lab command when delivery is requested; a completed
Lab audit can still leave assembly quality failed. Blender-only cases defer engines.
