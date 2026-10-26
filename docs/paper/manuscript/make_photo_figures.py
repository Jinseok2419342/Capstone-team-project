"""Compose the photo figures (2, 5, 6) of the manuscript from repository images.

All sources are real captures from the 2026-10-25 experiment or photos of the
device, stored under docs/presentation/final/images/.  Generated illustrations
(img-0*.png) are never used in the paper.  Output width is 1200 px, which is
above 300 dpi at the single-column width of the JDCS template (about 83 mm).
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SRC = ROOT / 'docs' / 'presentation' / 'final' / 'images'
OUT = HERE / 'figures'
WIDTH = 1200
GAP = 14


def _font(size):
    for path in ('C:/Windows/Fonts/arialbd.ttf',
                 '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _open(name, box=None):
    image = Image.open(SRC / name).convert('RGB')
    return image.crop(box) if box else image


def _row(images, width):
    """Scale images to one common height so the row fills `width` exactly."""
    ratios = [im.width / im.height for im in images]
    height = round((width - GAP * (len(images) - 1)) / sum(ratios))
    row = Image.new('RGB', (width, height), 'white')
    x = 0
    for i, (im, r) in enumerate(zip(images, ratios)):
        w = width - x if i == len(images) - 1 else round(height * r)
        row.paste(im.resize((w, height), Image.LANCZOS), (x, 0))
        x += w + GAP
    return row


def _label(image, text, xy=(10, 10)):
    draw = ImageDraw.Draw(image)
    font = _font(30)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    x, y = xy
    draw.rounded_rectangle((x, y, x + right - left + 16, y + bottom - top + 12), radius=6, fill='white')
    draw.text((x + 8 - left, y + 6 - top), text, font=font, fill='black')
    return image


def _stack(rows):
    height = sum(r.height for r in rows) + GAP * (len(rows) - 1)
    canvas = Image.new('RGB', (WIDTH, height), 'white')
    y = 0
    for r in rows:
        canvas.paste(r, (0, y))
        y += r.height + GAP
    return canvas


def figure_2():
    # (a) dashboard during the experiment, (b) inventory with AI names, categories and deadlines
    dashboard = _label(_row([_open('crops/dashboard.jpg', (90, 55, 1576, 1053))], WIDTH), '(a)')
    inventory = _label(_row([_open('crops/inventory.jpg', (90, 320, 1576, 985))], WIDTH), '(b)')
    return _stack([dashboard, inventory])


def figure_5():
    # (a) device on the stand, (b) camera view of the shelf during the experiment
    device = _open('device-stand.jpg', (0, 120, 908, 1210))
    view = _open('crops/cam-nine.jpg')
    row = _row([device, view], WIDTH)
    split = round(row.height * device.width / device.height)
    _label(row, '(a)')
    _label(row, '(b)', (split + GAP + 10, 10))
    return row


def figure_6():
    # (a) trial 33: scene before/after and the registered item image
    before, after = _open('crops/trial033_before.jpg'), _open('crops/trial033_after.jpg')
    crop = _open('crops/crop-soymilk.jpg')
    success = _row([before, after, crop], WIDTH)
    w = round(success.height * before.width / before.height)
    _label(success, '(a)')
    # (b) mug lying on its side, the item that failed most moves
    mug = _label(_row([_open('crops/cam-0826-mug.jpg', (0, 0, 990, 470))], WIDTH), '(b)')
    # (c) review list at the same time: nothing was recovered automatically
    review = _label(_row([_open('crops/review-row.jpg', (0, 0, 1472, 163))], WIDTH), '(c)', (WIDTH - 70, 8))
    return _stack([success, mug, review]), w


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    figure_2().save(OUT / 'figure-2.png', optimize=True)
    figure_5().save(OUT / 'figure-5.png', optimize=True)
    fig6, _ = figure_6()
    fig6.save(OUT / 'figure-6.png', optimize=True)
    for n in (2, 5, 6):
        path = OUT / f'figure-{n}.png'
        with Image.open(path) as im:
            print(path.relative_to(ROOT).as_posix(), im.size, f'{path.stat().st_size // 1024} KiB')


if __name__ == '__main__':
    main()
