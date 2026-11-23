"""Compare saved assembly revisions at the same camera without running Blender."""
import argparse
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

from review_packet import font


@lru_cache(maxsize=32)
def report(directory):
    return json.loads((directory / "geometry.json").read_text())


@lru_cache(maxsize=16)
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
        image = source.convert("RGB")
    pose = (camera["front"], view, spec["center"], spec["scale"], image.size, data.get("render_settings"))
    return image, pose, set(spec.get("hide", []))


@lru_cache(maxsize=12)
def capture(root, review, diagnostic, view, diagnostic_view, inner, threshold):
    dressed, pose, hidden = read_view(root, review, view)
    isolated, other_pose, other_hidden = read_view(
        root, diagnostic, diagnostic_view)
    if pose != other_pose or other_hidden != hidden | {inner} or inner in hidden:
        raise ValueError("Diagnostic must use the same camera and hide only the additional inner part")
    red, green, blue = ImageChops.difference(dressed, isolated).split()
    maximum = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    mask = np.asarray(maximum) > threshold
    return dressed, mask, pose, hidden


def text_lines(text, face, width):
    lines = [""]
    for word in text.split():
        line = (lines[-1] + " " + word).strip()
        if lines[-1] and face.getlength(line) > width:
            lines.append(word)
        else:
            lines[-1] = line
    return lines


def decision_queue(rows):
    """Group compatible observations; retain the exact evidence for every decision."""
    groups = {}
    for i, row in enumerate(rows):
        interface = row.get("interface", row["title"])
        key = (row["before"], row["after"], row["inner"], interface)
        item = groups.setdefault(key, dict(before=key[0], after=key[1], inner=key[2],
                                            interface=interface, evidence={}))
        if row["new"]:
            kind = "inspect_new"
        elif row["persistent"]:
            kind = "inspect_remaining"
        elif row["cleared"]:
            kind = "verify_clearance"
        else:
            kind = "no_visibility_difference"
        item["evidence"].setdefault(kind, []).append(i)
    order = ("inspect_new","inspect_remaining","verify_clearance","no_visibility_difference")
    for group in groups.values():
        evidence = group["evidence"]
        action = next(k for k in order if k in evidence)
        group["action"] = action
        # A small exposed fingertip can matter more than a large shirt patch.
        # Compare evidence only within this named interface and classification.
        metric = {"inspect_new":"new", "inspect_remaining":"persistent",
                  "verify_clearance":"cleared", "no_visibility_difference":"after_pixels"}
        group["first_rows"] = [max(evidence[k], key=lambda i: rows[i][metric[k]])
                               for k in order if k in evidence]
    return sorted(groups.values(), key=lambda g: order.index(g["action"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--font", type=Path)
    parser.add_argument("--guard-frame", action="store_true", help="Locate newly visible pixels outside all selected crops per view")
    args = parser.parse_args()
    conf = json.loads(args.plan.read_text())
    root = args.plan.resolve().parent
    threshold = conf["rgb_tolerance"]
    if type(threshold) is not int or not 0 <= threshold <= 255 or not conf["rows"]:
        raise ValueError("Provide a nonempty comparison and an 8-bit RGB tolerance")
    face = ImageFont.truetype(str(args.font), 19) if args.font else font(19)
    w, h = 280, 190
    panels, results, guards = [], [], []
    grouped = {}
    for row in conf["rows"]:
        key = tuple(row[k] for k in ("before","after","inner","view")) + (row.get("diagnostic_view", row["view"]),)
        grouped.setdefault(key, []).append(row["roi"])
    measured = set()
    for row in conf["rows"]:
        before, after, inner, view = (row[k] for k in ("before","after","inner","view"))
        diagnostic_view = row.get("diagnostic_view", view)
        def load(state_name):
            state = conf["states"][state_name]
            return capture(root, state["review"], state.get("diagnostic", state["review"]),
                           view, diagnostic_view, inner, threshold)
        a, old_full, pose, hidden = load(before)
        b, new_full, other_pose, other_hidden = load(after)
        if pose != other_pose or hidden != other_hidden:
            raise ValueError(f"Revision cameras or visibility differ for {view}")
        x, y, r, s = row["roi"]
        if not (0 <= x < r <= b.width and 0 <= y < s <= b.height):
            raise ValueError("ROI outside saved image")
        key = (before, after, inner, view, diagnostic_view)
        if args.guard_frame and key not in measured:
            # Pixels outside every planned crop for this interface still need visual triage.
            outside = new_full & ~old_full
            for left, top, right, bottom in grouped[key]:
                outside[top:bottom,left:right] = False
            yy, xx = np.nonzero(outside)
            guards.append(dict(before=before, after=after, inner=inner, view=view,
                               diagnostic_view=diagnostic_view, new_outside_rois=len(xx),
                               bbox=[int(xx.min()),int(yy.min()),int(xx.max()+1),int(yy.max()+1)] if len(xx) else None))
            measured.add(key)
        context = b.copy()
        ImageDraw.Draw(context).rectangle((x,y,r-1,s-1), outline="#ffe453", width=4)
        a, b = a.crop((x,y,r,s)), b.crop((x,y,r,s))
        old, new = old_full[y:s, x:r], new_full[y:s, x:r]
        overlay = np.array(b)
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
        for j,image in enumerate([context,a,b,Image.fromarray(overlay)]):
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
    out.save(args.output/"trace.png", compress_level=1)
    decisions = decision_queue(results)
    if args.guard_frame:
        lines = ["# Rework decisions", "", "Row numbers refer to trace.png, starting at 1.", ""]
        for item in decisions:
            evidence = [str(i+1) for i in item["first_rows"]]
            lines.append(f"- {item['before']} → {item['after']} · {item['interface']} · "
                         f"{item['action']} · start with row(s) {', '.join(evidence)}")
        for check in guards:
            if check["new_outside_rois"]:
                lines.append(f"- Inspect outside the planned crops · {check['before']} → {check['after']} · "
                             f"{check['view']} · {check['new_outside_rois']} px · {check['bbox']}")
        (args.output/"decisions.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    (args.output/"trace.json").write_text(json.dumps(dict(rgb_tolerance=threshold,rows=results,frame_checks=guards,decisions=decisions),
                                                       indent=2,ensure_ascii=False))


if __name__ == "__main__":
    main()
