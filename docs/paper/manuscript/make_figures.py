"""Make the six manuscript figures as JPEG files (JDCS template: figures are
inserted as jpg, and text inside a figure is in English).

Figures 1, 3 and 4 are schematics drawn here.  Figures 2, 5 and 6 are composed
from real captures of the 2026-10-25 experiment and photos of the device under
docs/presentation/final/images/.  Generated illustrations (img-0*.png) are
never used in the paper.

Output width is 1200 px, about 376 dpi at the single-column width of the JDCS
template (81 mm).  Figures 2 and 6 show the Korean web interface as it is; the
manuscript gives the reason in an English note between the figure and its
caption, as the template requires.
"""
from pathlib import Path
import math

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SRC = ROOT / 'docs' / 'presentation' / 'final' / 'images'
OUT = HERE / 'figures'
WIDTH = 1200
GAP = 14
COLUMN_MM = 81
DPI = round(WIDTH / (COLUMN_MM / 25.4))

INK = '#243746'
MUTED = '#5A6671'
LIGHT = '#F0F4F6'
EDGE = '#AEBBC4'

FONTS = {
    False: ('C:/Windows/Fonts/arial.ttf', '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
    True: ('C:/Windows/Fonts/arialbd.ttf', '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
           '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
}


def _font(size, bold=True):
    for path in FONTS[bold]:
        if Path(path).exists():
            return ImageFont.truetype(path, round(size))
    return ImageFont.load_default()


# ---------- schematics (figures 1, 3, 4) ----------

class Sketch:
    """Small drawing surface in points (y grows upward), rendered at 1200 px."""

    def __init__(self, width_pt, height_pt):
        self.k = WIDTH / width_pt
        self.h = height_pt
        self.image = Image.new('RGB', (WIDTH, round(height_pt * self.k)), 'white')
        self.draw = ImageDraw.Draw(self.image)

    def _xy(self, x, y):
        return x * self.k, (self.h - y) * self.k

    def _fit(self, text, size, bold, max_width):
        font = _font(size * self.k, bold)
        while self.draw.textlength(text, font=font) > max_width * self.k and size > 4:
            size -= 0.2
            font = _font(size * self.k, bold)
        return font

    def text(self, x, y, text, size=6.6, bold=False, fill=MUTED, max_width=1e9):
        font = self._fit(text, size, bold, max_width)
        self.draw.text(self._xy(x, y), text, font=font, fill=fill, anchor='mm')

    def box(self, x, y, w, h, lines, accent=False, size=7.2):
        (x0, y1), (x1, y0) = self._xy(x, y), self._xy(x + w, y + h)
        self.draw.rounded_rectangle((x0, y0, x1, y1), radius=2 * self.k, fill=INK if accent else LIGHT,
                                    outline=EDGE, width=max(1, round(.6 * self.k)))
        pitch = size + 2.8
        for i, line in enumerate(lines):
            cy = y + h / 2 + (len(lines) - 1) * pitch / 2 - i * pitch
            self.text(x + w / 2, cy, line, size, bold=(i == 0), fill='white' if accent else INK, max_width=w - 8)

    def arrow(self, x1, y1, x2, y2):
        self.draw.line([self._xy(x1, y1), self._xy(x2, y2)], fill=MUTED, width=max(1, round(.9 * self.k)))
        a, z = math.atan2(y2 - y1, x2 - x1), 4.0
        self.draw.polygon([self._xy(x2, y2),
                           self._xy(x2 - z * math.cos(a - .45), y2 - z * math.sin(a - .45)),
                           self._xy(x2 - z * math.cos(a + .45), y2 - z * math.sin(a + .45))], fill=MUTED)


W_PT = 230  # schematic width in points (one column)


def figure_1():
    w, s = W_PT, Sketch(W_PT, 214)
    s.box(30, 184, w - 60, 26, ['CSI camera', 'Video input (Picamera2)'])
    s.arrow(w / 2, 184, w / 2, 170)
    s.box(0, 122, w, 48, ['Raspberry Pi 4 (2 GB)', 'Stable-scene check, alignment, illumination compensation',
                           'Matching with registered items → event decision'], True)
    left, right = w * .41, w * .56
    s.arrow(left / 2, 122, left / 2, 106)
    s.arrow(w - right / 2, 122, w - right / 2, 106)
    s.box(0, 66, left, 40, ['Movement · Removal', 'Handled on the device', 'No external call'])
    s.box(w - right, 66, right, 40, ['Placement · Removal verification', 'External vision-language model',
                                     'Up to four before/after images'])
    s.arrow(left / 2, 66, left / 2, 50)
    s.arrow(w - right / 2, 66, w - right / 2, 50)
    s.box(0, 6, w, 44, ['FastAPI · SQLite (WAL)', 'Provisional records · retention periods · history',
                        'Administrator web interface · notifications'])
    return s.image


def figure_3():
    w, s = W_PT, Sketch(W_PT, 118)
    bw, bh = 70, 32
    xs = (0, (w - bw) / 2, w - bw)
    top, low = 82, 26
    s.box(xs[0], top, bw, bh, ['Camera ready', 'Set reference scene'])
    s.box(xs[1], top, bw, bh, ['Monitoring', 'Motion or change'])
    s.box(xs[2], top, bw, bh, ['Waiting', '3.0 s after last motion'])
    s.box(xs[2], low, bw, bh, ['Stability check', 'No motion for 1.2 s'])
    s.box(xs[1], low, bw, bh, ['Analysis', 'Compare before/after'], True)
    s.arrow(xs[0] + bw, top + bh / 2, xs[1], top + bh / 2)
    s.arrow(xs[1] + bw, top + bh / 2, xs[2], top + bh / 2)
    s.arrow(xs[2] + bw / 2, top, xs[2] + bw / 2, low + bh)
    s.arrow(xs[2], low + bh / 2, xs[1] + bw, low + bh / 2)
    s.arrow(xs[1] + bw / 2, low + bh, xs[1] + bw / 2, top)
    s.text(xs[0] + bw / 2, low + bh / 2 + 5, 'After DB commit:', max_width=bw)
    s.text(xs[0] + bw / 2, low + bh / 2 - 4, 'update reference', max_width=bw)
    s.text(w / 2, 9, 'Motion during the stability check returns to waiting')
    return s.image


def figure_4():
    steps = [
        (['Stable before/after images', 'Reference image B / current image I'], False),
        (['Geometric alignment', 'Optical flow tracking + RANSAC partial affine'], False),
        (['Difference image', 'Exposure and illumination compensation, color difference'], False),
        (['Candidate refinement', 'Common-edge and shadow suppression, morphology'], False),
        (['Global change check', 'No event if the change exceeds 42% of the frame'], False),
        (['Matching with registered items → event decision', 'Placement / movement / removal / removal verification'], True),
    ]
    bh, gap = 26, 9
    height = len(steps) * bh + (len(steps) - 1) * gap + 4
    w, s = W_PT, Sketch(W_PT, height)
    for i, (lines, accent) in enumerate(steps):
        y = height - 2 - (i + 1) * bh - i * gap
        s.box(14, y, w - 28, bh, lines, accent)
        if i:
            s.arrow(w / 2, y + bh + gap, w / 2, y + bh)
    return s.image


# ---------- photo figures (2, 5, 6) ----------

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
    success = _label(_row([before, after, crop], WIDTH), '(a)')
    # (b) mug lying on its side, the item that failed most moves
    mug = _label(_row([_open('crops/cam-0826-mug.jpg', (0, 0, 990, 470))], WIDTH), '(b)')
    # (c) review list at the same time: nothing was recovered automatically
    review = _label(_row([_open('crops/review-row.jpg', (0, 0, 1472, 163))], WIDTH), '(c)', (WIDTH - 70, 8))
    return _stack([success, mug, review])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    makers = {1: figure_1, 2: figure_2, 3: figure_3, 4: figure_4, 5: figure_5, 6: figure_6}
    for n, make in makers.items():
        path = OUT / f'figure-{n}.jpg'
        make().save(path, 'JPEG', quality=95, subsampling=0, dpi=(DPI, DPI), optimize=True)
        with Image.open(path) as im:
            print(path.relative_to(ROOT).as_posix(), im.size, f'{path.stat().st_size // 1024} KiB')


if __name__ == '__main__':
    main()
