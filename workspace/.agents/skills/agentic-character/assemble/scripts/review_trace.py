"""Compare saved assembly revisions at the same camera without running Blender."""
import argparse
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

from review_packet import font


@lru_cache(maxsize=32)
def report(directory):
    return json.loads((directory / "geometry.json").read_text())


def read_view(root, directory, selector):
    frame, view = selector.split("=")
    folder = (root / directory).resolve()
    data = report(folder)
    filename = f"{frame}-{view}.png"
    if filename not in data["images"]:
        raise ValueError(f"Saved review does not include {selector} in {folder}")
    camera = data["frames"]
    spec = camera["frames"][frame]
    with Image.open(folder / filename) as source:
        image = np.array(source.convert("RGB"))
    pose = (camera["front"], view, spec["center"], spec["scale"], image.shape, data.get("render_settings"))
    return image, pose, set(spec.get("hide", []))


def capture(root, state, row):
    dressed, pose, hidden = read_view(root, state["review"], row["view"])
    isolated, other_pose, other_hidden = read_view(
        root, state.get("diagnostic", state["review"]), row.get("diagnostic_view", row["view"]))
    if pose != other_pose or other_hidden != hidden | {row["inner"]} or row["inner"] in hidden:
        raise ValueError("Diagnostic must use the same camera and hide only the additional inner part")
    return dressed, isolated, pose, hidden


def text_lines(text, face, width):
    lines = [""]
    for word in text.split():
        line = (lines[-1] + " " + word).strip()
        if lines[-1] and face.getlength(line) > width:
            lines.append(word)
        else:
            lines[-1] = line
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--font", type=Path)
    args = parser.parse_args()
    conf = json.loads(args.plan.read_text())
    root = args.plan.resolve().parent
    threshold = conf["rgb_tolerance"]
    if type(threshold) is not int or not 0 <= threshold <= 255 or not conf["rows"]:
        raise ValueError("Provide a nonempty comparison and an 8-bit RGB tolerance")
    face = ImageFont.truetype(str(args.font), 19) if args.font else font(19)
    w, h = 280, 190
    panels, results = [], []
    for row in conf["rows"]:
        a, ai, pose, hidden = capture(root, conf["states"][row["before"]], row)
        b, bi, other_pose, other_hidden = capture(root, conf["states"][row["after"]], row)
        if pose != other_pose or hidden != other_hidden:
            raise ValueError(f"Revision cameras or visibility differ for {row['view']}")
        x, y, r, s = row["roi"]
        if not (0 <= x < r <= b.shape[1] and 0 <= y < s <= b.shape[0]):
            raise ValueError("ROI outside saved image")
        context = Image.fromarray(b)
        ImageDraw.Draw(context).rectangle((x,y,r-1,s-1), outline="#ffe453", width=4)
        a, ai, b, bi = [v[y:s, x:r] for v in (a, ai, b, bi)]
        old, new = [np.max(np.abs(v.astype(np.int16)-iso), axis=2)>threshold
                    for v, iso in [(a,ai),(b,bi)]]
        overlay = b.copy()
        masks = {"new": new & ~old, "persistent": old & new, "cleared": old & ~new}
        for mask, color in zip(masks.values(), [(255,44,86),(255,184,35),(34,191,204)]):
            overlay[mask] = color
        stats = {key:int(mask.sum()) for key,mask in masks.items()}
        results.append(dict(**row, before_pixels=int(old.sum()), after_pixels=int(new.sum()),
                            render_settings_recorded=pose[-1] is not None, **stats))
        heading = f"{row['title']}   |   {row['before']} → {row['after']}   |   {row['view']}"
        numbers = f"{int(old.sum())} → {int(new.sum())} px     +{stats['new']}   ={stats['persistent']}   −{stats['cleared']}"
        notes = text_lines(row.get("note", ""), face, 4*w-18)
        top = 56+26*len(notes)
        panel = Image.new("RGB", (4*w, top+h), "white")
        draw = ImageDraw.Draw(panel)
        for j,line in enumerate([heading,numbers,*notes]):
            draw.text((8,4+26*j),line,font=face,fill="#142c40")
        for j,image in enumerate([context,Image.fromarray(a),Image.fromarray(b),Image.fromarray(overlay)]):
            tile = ImageOps.contain(image,(w-4,h-4),Image.Resampling.LANCZOS)
            panel.paste(tile,(j*w+(w-tile.width)//2,top+(h-tile.height)//2))
        panels.append(panel)
    out = Image.new("RGB",(4*w,70+sum(p.height for p in panels)),"white")
    draw = ImageDraw.Draw(out)
    for j,title in enumerate(conf.get("columns", ["ROI in current view","Before","After","Visibility changes"])):
        draw.text((j*w+6,8),title,font=face,fill="#142c40")
    for j,(name,color) in enumerate(zip(conf.get("legend",["New","Persistent","Cleared"]),
                                        ["#ff2c56","#ffb823","#22bfcc"])):
        draw.rectangle((8+175*j,41,24+175*j,56),fill=color)
        draw.text((30+175*j,37),name,font=face,fill="#142c40")
    pos=70
    for panel in panels:
        out.paste(panel,(0,pos))
        pos+=panel.height
    args.output.mkdir(parents=True,exist_ok=False)
    out.save(args.output/"trace.png")
    (args.output/"trace.json").write_text(json.dumps(dict(rgb_tolerance=threshold,rows=results),
                                                       indent=2,ensure_ascii=False))


if __name__ == "__main__":
    main()
