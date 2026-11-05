#!/usr/bin/env python3
"""Render assets/hero.gif: an amber oscilloscope sweep that lights up the name.

The beam reveals a pre-rendered "finished" screen column by column, so every frame
is a cheap crop-and-paste and the GIF only stores the band that changed.

Usage: make_hero.py OUTPUT.gif   (needs Pillow; only run by hand, never in CI)
"""
import math
import random
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

W, H = 1280, 440
S = 2  # layers are drawn at 2x, then downsampled, for clean anti-aliasing

BG = (12, 11, 8)
GRID = (32, 28, 18)
GRID_MAJOR = (46, 40, 24)
OFF_DOT = (31, 26, 12)
AMBER = (255, 176, 0)
HOT = (255, 236, 190)
DIM = (168, 128, 52)
TEAL = (79, 209, 197)

PLOT = (56, 196, 1224, 352)  # x0, y0, x1, y1
RESID = (362, 386)  # y band of the residual strip

MENLO = "/System/Library/Fonts/Menlo.ttc"
MOTTO = "the program never reports a number the data cannot support."

GLYPHS = {
    "J": "00111 00010 00010 00010 00010 10010 01100",
    "O": "01110 10001 10001 10001 10001 10001 01110",
    "N": "10001 11001 10101 10101 10011 10001 10001",
    "G": "01110 10001 10000 10111 10001 10001 01110",
    "S": "01111 10000 10000 01110 00001 00001 11110",
    "U": "10001 10001 10001 10001 10001 10001 01110",
    "K": "10001 10010 10100 11000 10100 10010 10001",
    "I": "01110 00100 00100 00100 00100 00100 01110",
    "-": "00000 00000 00000 11111 00000 00000 00000",
}
TITLE = "JONGSU-KING"
PITCH = 12  # dot spacing in px
TITLE_XY = (56, 62)

# The techniques the apps actually handle. Positions and heights are decorative.
PEAKS = [
    ("J-V", 0.055, 0.62),
    ("EQE", 0.150, 0.40),
    ("Abs", 0.235, 0.74),
    ("PL", 0.325, 0.48),
    ("Raman", 0.415, 0.92),
    ("FTIR", 0.505, 0.56),
    ("XRD", 0.590, 1.00),
    ("SEM", 0.680, 0.36),
    ("XPS", 0.765, 0.68),
    ("NMR", 0.855, 0.84),
    ("T-S", 0.945, 0.52),
]


def font(size, bold=False):
    return ImageFont.truetype(MENLO, size * S, index=1 if bold else 0)


def scaled(*xs):
    return [x * S for x in xs]


def graticule(draw):
    x0, y0, x1, y1 = PLOT
    for i in range(13):
        x = x0 + (x1 - x0) * i / 12
        draw.line(scaled(x, y0, x, y1), fill=GRID, width=S)
    for i in range(5):
        y = y0 + (y1 - y0) * i / 4
        draw.line(scaled(x0, y, x1, y), fill=GRID, width=S)
    draw.line(scaled(x0, y1, x1, y1), fill=GRID_MAJOR, width=2 * S)
    for i in range(61):
        x = x0 + (x1 - x0) * i / 60
        tick = 7 if i % 5 == 0 else 3
        draw.line(scaled(x, y1, x, y1 + tick), fill=GRID_MAJOR, width=S)


def dots():
    """Yield (x, y) centres for every cell of the title, lit or not."""
    col = 0
    for ch in TITLE:
        rows = GLYPHS[ch].split()
        for r, row in enumerate(rows):
            for c, cell in enumerate(row):
                yield TITLE_XY[0] + (col + c) * PITCH, TITLE_XY[1] + r * PITCH, cell == "1"
        col += 6


def add_glow(base, mask, color, radius, strength):
    glow = mask.filter(ImageFilter.GaussianBlur(radius * S))
    glow = glow.point(lambda v: min(255, int(v * strength)))
    base.paste(color, (0, 0), glow)
    base.paste(color, (0, 0), mask)


def spectrum():
    """Return [(x, y)] in px: pseudo-Voigt peaks on an amorphous hump, plus noise."""
    x0, y0, x1, y1 = PLOT
    rng = random.Random(7)
    span = x1 - x0
    out = []
    for px in range(int(x0), int(x1) + 1):
        t = (px - x0) / span
        v = 0.05 + 0.07 * math.exp(-(((t - 0.22) / 0.13) ** 2)) + 0.05 * math.exp(-(((t - 0.72) / 0.2) ** 2))
        for _, c, h in PEAKS:
            d = (t - c) / 0.0052
            v += h * 0.76 * (0.55 / (1 + d * d) + 0.45 * math.exp(-0.5 * d * d))
        v += rng.gauss(0, 0.006)
        out.append((px, y1 - max(0.0, v) * (y1 - y0)))
    return out


def residual():
    x0, _, x1, _ = PLOT
    rng = random.Random(11)
    mid = sum(RESID) / 2
    out = []
    for px in range(int(x0), int(x1) + 1):
        t = (px - x0) / (x1 - x0)
        near = max(math.exp(-(((t - c) / 0.012) ** 2)) for _, c, _ in PEAKS)
        out.append((px, mid + rng.gauss(0, 1.1 + 5.5 * near)))
    return out


def build_screens():
    off = Image.new("RGB", (W * S, H * S), BG)
    d = ImageDraw.Draw(off)
    graticule(d)
    d.text(scaled(56, 24), "CH1  INTENSITY (a.u.)", font=font(14), fill=DIM)
    for x, y, _ in dots():
        r = 4.2
        d.ellipse(scaled(x - r, y - r, x + r, y + r), fill=OFF_DOT)

    lit = off.copy()
    dot_mask = Image.new("L", lit.size, 0)
    dm = ImageDraw.Draw(dot_mask)
    for x, y, on in dots():
        if on:
            r = 4.6
            dm.ellipse(scaled(x - r, y - r, x + r, y + r), fill=255)
    add_glow(lit, dot_mask, AMBER, 7, 0.75)

    d = ImageDraw.Draw(lit)
    d.text(scaled(56, 158), "scientific software // desktop apps, datasets, an iPhone golf lab", font=font(16), fill=DIM)
    panel = [("BENCH", "physiscore  xrd  nmr  calc"), ("DATA", "OPV-DB"), ("OCEAN", "SUYA"), ("TEE", "SwingLab")]
    for i, (k, v) in enumerate(panel):
        y = 62 + i * 21
        d.text(scaled(868, y), k, font=font(14, bold=True), fill=AMBER)
        d.text(scaled(930, y), v, font=font(14), fill=DIM)

    def with_trace(color, glow_radius, glow_strength):
        img = lit.copy()
        mask = Image.new("L", img.size, 0)
        m = ImageDraw.Draw(mask)
        m.line([tuple(scaled(x, y)) for x, y in spectrum()], fill=255, width=2 * S, joint="curve")
        add_glow(img, mask, color, glow_radius, glow_strength)
        res = Image.new("L", img.size, 0)
        ImageDraw.Draw(res).line([tuple(scaled(x, y)) for x, y in residual()], fill=170, width=S)
        img.paste(TEAL, (0, 0), res)

        draw = ImageDraw.Draw(img)
        x0, y0, x1, y1 = PLOT
        trace = spectrum()
        for name, c, _ in PEAKS:
            px = x0 + (x1 - x0) * c
            top = min(y for x, y in trace if abs(x - px) < 3)
            size = draw.textlength(name, font=font(14, bold=True)) / S
            draw.text(scaled(px - size / 2, top - 22), name, font=font(14, bold=True), fill=color)
        return img

    done = with_trace(AMBER, 5, 0.8)
    hot = with_trace(HOT, 9, 1.0)
    down = lambda im: im.resize((W, H), Image.LANCZOS)
    motto = done.copy()
    ImageDraw.Draw(motto).text(scaled(56, 404), "> " + MOTTO, font=font(16, bold=True), fill=AMBER)
    return down(off), down(done), down(hot), down(motto)


def beam_strip():
    half = 34
    strip = Image.new("RGB", (half * 2 + 1, H), (0, 0, 0))
    d = ImageDraw.Draw(strip)
    for dx in range(-half, half + 1):
        k = (1 - abs(dx) / half) ** 3 * 0.42
        if dx == 0:
            k = 1.0
        d.line([(dx + half, 0), (dx + half, H)], fill=tuple(int(c * k) for c in HOT))
    return strip


def frame_at(bx, off, done, hot, strip):
    """Compose the screen with the beam at column bx."""
    img = off.copy()
    if bx > 0:
        img.paste(done.crop((0, 0, bx, H)), (0, 0))
        trail = min(bx, 190)
        ramp = Image.linear_gradient("L").rotate(90, expand=True).resize((trail, H))
        img.paste(hot.crop((bx - trail, 0, bx, H)), (bx - trail, 0), ramp)
    half = strip.width // 2
    left = max(0, bx - half)
    right = min(W, bx + half + 1)
    if right > left:
        region = img.crop((left, 0, right, H))
        part = strip.crop((left - (bx - half), 0, right - (bx - half), H))
        img.paste(ImageChops.add(region, part), (left, 0))
    return img


def ramp(a, b, n):
    return [tuple(round(a[i] + (b[i] - a[i]) * k / (n - 1)) for i in range(3)) for k in range(n)]


def palette_image():
    colors = ramp(BG, AMBER, 44) + ramp(AMBER, HOT, 16) + ramp(HOT, (255, 255, 255), 4)
    colors += ramp(BG, TEAL, 12) + ramp(BG, DIM, 14) + [GRID, GRID_MAJOR, OFF_DOT]
    flat = [v for c in colors for v in c]
    flat += flat[:3] * (256 - len(colors))
    pal = Image.new("P", (1, 1))
    pal.putpalette(flat)
    return pal


def main(path):
    off, done, hot, motto = build_screens()
    strip = beam_strip()
    pal = palette_image()
    frames, delays = [], []

    def push(img, ms):
        frames.append(img.quantize(palette=pal, dither=Image.Dither.NONE))
        delays.append(ms)

    # Frame 0 is what paused or reduced-motion viewers see, so it must be the finished
    # screen. The loop then starts by decaying it, not by going dark.
    push(motto, 3200)
    for i in range(1, 7):
        push(Image.blend(motto, off, i / 6), 60)
    push(off, 400)
    sweep = 66
    for i in range(sweep + 1):
        push(frame_at(round(W * i / sweep), off, done, hot, strip), 40)
    # The beam has left the screen: type the motto one or two characters at a time.
    char_w = 16 * 0.602
    prefix = len("> ")
    for n in range(prefix, prefix + len(MOTTO) + 1, 2):
        img = done.copy()
        reveal = int(56 + n * char_w)
        img.paste(motto.crop((0, 396, reveal, 432)), (0, 396))
        push(img, 40)
    cursor_x = int(56 + (prefix + len(MOTTO)) * char_w) + 4
    for i in range(4):
        img = motto.copy()
        if i % 2 == 0:
            ImageDraw.Draw(img).rectangle((cursor_x, 406, cursor_x + 9, 423), fill=AMBER)
        push(img, 460)

    frames[0].save(path, save_all=True, append_images=frames[1:], duration=delays, loop=0, disposal=1)


if __name__ == "__main__":
    main(sys.argv[1])
