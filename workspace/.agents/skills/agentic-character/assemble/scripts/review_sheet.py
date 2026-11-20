"""Compose an unmasked four-view review from two matched assembly renders."""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

VIEWS = ('front', 'left', 'back', 'right')


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
    main()
