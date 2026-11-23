"""Compose an unmasked four-view review from two matched assembly renders."""
import argparse
from html import escape
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

VIEWS = ('front', 'left', 'back', 'right')


def overview(argv):
    """Render one camera plan and index the unchanged, full-resolution source views."""
    parser = argparse.ArgumentParser(description=overview.__doc__)
    parser.add_argument("scene", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--blender", default="blender")
    args = parser.parse_args(argv)
    plan = json.loads(args.plan.read_text())
    if "review_groups" in plan:
        from review_packet import render_packet
        render_packet(args, plan)
        return
    keys = [f"full={view}" for view in VIEWS] + plan["overview"]
    if len(keys) == 4 or len(set(keys)) != len(keys):
        parser.error("Choose at least one distinct close-up in overview")
    tiles = []
    for key in keys:
        frame, _, view = key.partition("=")
        options = plan["frames"].get(frame)
        diagonals = ("front_left", "back_left", "back_right", "front_right")
        if options is None or (view not in VIEWS and
                               not (options.get("diagonals") and view in diagonals)):
            parser.error(f"View unavailable in camera plan: {key}")
        tiles.append((key, f"{frame}-{view}.png"))
    renderer = Path(__file__).with_name("review_views.py")
    subprocess.run([args.blender, "-b", args.scene, "--python-exit-code", "1",
                    "-P", renderer, "--", args.plan, args.output], check=True)
    cell, header = 360, 26
    sheet = Image.new("RGB", (4*cell, ((len(tiles)+3)//4)*(cell+header)), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (key, filename) in enumerate(tiles):
        x = (index % 4)*cell
        y = (index // 4)*(cell+header)
        with Image.open(args.output/filename) as source:
            pic = ImageOps.contain(source.convert("RGB"), (cell, cell), Image.Resampling.LANCZOS)
        sheet.paste(pic, (x+(cell-pic.width)//2, y+header+(cell-pic.height)//2))
        draw.text((x+6, y+6), key, fill="black")
    sheet.save(args.output/"overview.jpg", quality=94)
    links = []
    for key, filename in tiles:
        link = escape(filename, quote=True)
        links.append(f'<a href="{link}"><span>{escape(key)}</span><img src="{link}" alt="{escape(key, quote=True)}"></a>')
    (args.output/"overview.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>Assembly review</title>'
        '<style>body{font:16px system-ui;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}'
        'a{color:inherit}img{display:block;width:100%}</style>' + ''.join(links), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--references', nargs=4, type=Path, metavar='IMAGE')
    args = parser.parse_args()
    rows = []
    if args.references:
        rows.append(('Reference', args.references))
    for label, folder in [('Before', args.before), ('After', args.after)]:
        rows.append((label, [folder / f'full-{view}.png' for view in VIEWS]))
    cell, margin, header = 350, 96, 32
    sheet = Image.new('RGB', (margin + 4 * cell, header + len(rows) * cell), '#f4f4f4')
    draw = ImageDraw.Draw(sheet)
    for i, view in enumerate(VIEWS):
        draw.text((margin + (i + .46) * cell, 10), view.title(), fill='black')
    for j, (label, paths) in enumerate(rows):
        y = header + j * cell
        draw.text((10, y + cell // 2), label, fill='black')
        for i, path in enumerate(paths):
            with Image.open(path) as src:
                pic = ImageOps.contain(src.convert('RGB'), (cell, cell), Image.Resampling.LANCZOS)
            sheet.paste(pic, (margin + i * cell + (cell-pic.width)//2, y+(cell-pic.height)//2))
    sheet.save(args.output)


if __name__ == '__main__':
    if sys.argv[1:2] == ['overview']:
        overview(sys.argv[2:])
    else:
        main()
