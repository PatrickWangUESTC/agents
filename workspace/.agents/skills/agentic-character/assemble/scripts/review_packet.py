"""Compose full views and matched interface crops as one illustrated review packet."""
from html import escape
from pathlib import Path
import subprocess

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps


def font(size):
    for name in ("DejaVuSans.ttf", "Arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_packet(args, plan):
    frames = plan["frames"]
    if frames["full"].get("hide"):
        raise ValueError("Full-character views must include all parts")
    groups = [("Full character", [(f"full={d}", d.title()) for d in ("front", "left", "back", "right")])]
    if not plan["review_groups"]:
        raise ValueError("Choose at least one applicable interface")
    for group in plan["review_groups"]:
        if not group["title"] or not group["views"]:
            raise ValueError("Each review group needs a title and at least one view")
        groups.append((group["title"], [(v["view"], v["check"]) for v in group["views"]]))
    comparisons = {}
    for group in plan["review_groups"]:
        for tile in group["views"]:
            if "compare_with" in tile:
                a, va = tile["view"].split("=")
                b, vb = tile["compare_with"].split("=")
                if (va != vb or any(frames[a][k] != frames[b][k] for k in ("center","scale"))
                        or not set(frames[a].get("hide", [])) < set(frames[b].get("hide", []))):
                    raise ValueError("Visibility comparisons need matched cameras and an additionally hidden layer")
                tolerance = tile["rgb_tolerance"]
                if type(tolerance) is not int or not 0 <= tolerance <= 255:
                    raise ValueError("Expected an 8-bit RGB tolerance")
                comparisons[(group["title"], tile["view"])] = (b, vb, tolerance)
    selectors = list(dict.fromkeys(k for _, entries in groups for k, _ in entries))
    for b, vb, _ in comparisons.values():
        if f"{b}={vb}" not in selectors:
            raise ValueError("Include the diagnostic counterpart in the review packet")
    reference = plan.get("review_reference")
    if reference:
        with Image.open(args.plan.parent / reference) as source:
            reference = source.convert("RGB")
    renderer = Path(__file__).with_name("review_views.py")
    subprocess.run([args.blender, "-b", args.scene, "--python-exit-code", "1", "-P", renderer,
                    "--", args.plan, args.output, "--audit", "--focus", *selectors], check=True)

    cell, heading = 360, 40
    title_font, label_font, small_font = font(20), font(16), font(13)
    pages, html = [], ['<!doctype html><meta charset="utf-8"><title>Assembly review</title>'
                       '<style>body{font:16px system-ui;margin:1rem}section{display:grid;'
                       'grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:8px}'
                       'img{max-width:100%}a{display:block;color:inherit}small{display:block}</style>']
    if reference is not None:
        reference.thumbnail((4*cell, 420), Image.Resampling.LANCZOS)
        reference.save(args.output/"reference.jpg", quality=95)
        refpage = Image.new("RGB", (4*cell, reference.height+heading), "white")
        ImageDraw.Draw(refpage).text((8, 8), "A-pose reference", font=title_font, fill="black")
        refpage.paste(reference, ((refpage.width-reference.width)//2, heading))
        pages.append(refpage)
        html.append('<h2>A-pose reference</h2><img src="reference.jpg" alt="A-pose reference">')
    for i, (title, entries) in enumerate(groups):
        cards = []
        html.extend([f'<h2>{escape(title)}</h2>', '<section>'])
        for key, check in entries:
            frame, view = key.split("=")
            hidden = frames[frame].get("hide", [])
            context = key + (" | hidden: " + ", ".join(hidden) if hidden else "")
            filename = f"{frame}-{view}.png"
            with Image.open(args.output/filename) as source:
                full = source.convert("RGB")
            comparison = comparisons.get((title, key))
            preview = filename
            if comparison:
                other, direction, tolerance = comparison
                with Image.open(args.output/f"{other}-{direction}.png") as src:
                    difference = ImageChops.difference(full, src.convert("RGB"))
                red, green, blue = difference.split()
                mask = ImageChops.lighter(ImageChops.lighter(red, green), blue).point(
                    lambda x: 255 if x > tolerance else 0)
                count = mask.histogram()[255]
                context += f" | {count} px (RGB delta > {tolerance})"
                if mask.getbbox():
                    ImageDraw.Draw(full).rectangle(mask.getbbox(), outline="#ff3377", width=3)
                preview = f"check-{i}-{len(cards)}.png"
                full.save(args.output/preview)
            image = ImageOps.contain(full, (cell, cell), Image.Resampling.LANCZOS)
            card = Image.new("RGB", (cell, cell+64), "white")
            draw = ImageDraw.Draw(card)
            # Keep long descriptions readable on the portable sheets as well as in HTML.
            lines = []
            for text, face in [(check, label_font), (context, small_font)]:
                line = ""
                for word in text.split():
                    candidate = (line+" "+word).strip()
                    if line and draw.textlength(candidate, font=face) > cell-12:
                        lines.append((line, face))
                        line = word
                    else:
                        line = candidate
                lines.append((line, face))
            header = max(64, 8+22*len(lines))
            card = Image.new("RGB", (cell, cell+header), "white")
            draw = ImageDraw.Draw(card)
            for j, (line, face) in enumerate(lines):
                draw.text((6, 4+j*22), line, font=face, fill="#191919")
            card.paste(image, ((cell-image.width)//2, header))
            cards.append(card)
            link = escape(filename, quote=True)
            html.append(f'<a href="{link}">{escape(check)}<small>{escape(context)}</small>'
                        f'<img src="{escape(preview, quote=True)}" alt="{escape(check, quote=True)}"></a>')
        html.append('</section>')
        row_height = max(card.height for card in cards)
        page = Image.new("RGB", (4*cell, heading+((len(cards)+3)//4)*row_height), "white")
        ImageDraw.Draw(page).text((8, 8), title, font=title_font, fill="black")
        for j, card in enumerate(cards):
            page.paste(card, ((j%4)*cell, heading+(j//4)*row_height))
        page.save(args.output/f"group-{i:02}.jpg", quality=95)
        pages.append(page)
    sheet = Image.new("RGB", (4*cell, sum(p.height for p in pages)), "white")
    top = 0
    for page in pages:
        sheet.paste(page, (0, top))
        top += page.height
    sheet.save(args.output/"overview.jpg", quality=95)
    html.append('<p><a href="geometry.json">Geometry measurements and camera settings</a></p>')
    (args.output/"overview.html").write_text("".join(html), encoding="utf-8")
