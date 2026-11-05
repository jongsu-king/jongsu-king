#!/usr/bin/env python3
"""Render assets/hero-{dark,light}.gif: one powder pattern on two period instruments.

Dark mode is an oscilloscope, light mode a chart recorder with a dot-matrix head. The
pattern is calculated, not decorative: cubic alpha-FAPbI3 from its structure factors.

The beam reveals a pre-rendered finished sheet column by column, so every frame is a
cheap crop-and-paste and the GIF only stores the band that changed.

Usage: make_hero.py OUTPUT_DIR   (needs Pillow; only run by hand, never in CI)
"""
import itertools
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

W, H = 1280, 440
S = 2  # layers are drawn at 2x, then downsampled, for clean anti-aliasing
PLOT = (56, 188, 1224, 368)  # x0, y0, x1, y1
TWO_THETA = (10.0, 52.0)
MENLO = "/System/Library/Fonts/Menlo.ttc"
HEADER = ["α-FAPbI3   Pm-3m", "a = 6.36 Å   Cu Kα", "simulated pattern"]

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
PITCH = 11
TITLE_XY = (58, 62)

DARK = {
    "name": "dark", "bg": (11, 11, 9), "minor": (28, 26, 18), "major": (46, 41, 26), "off_dot": (29, 25, 13),
    "title": (255, 176, 0), "trace": (255, 176, 0), "text": (176, 136, 58), "label": (255, 196, 70), "hot": (255, 232, 180),
}
LIGHT = {
    "name": "light", "bg": (248, 243, 231), "minor": (241, 224, 210), "major": (229, 187, 164), "off_dot": None,
    "title": (31, 33, 40), "trace": (32, 44, 96), "text": (70, 66, 62), "label": (32, 44, 96), "hot": (32, 44, 96),
}


def font(size, bold=False):
    return ImageFont.truetype(MENLO, size * S, index=1 if bold else 0)


def scaled(*xs):
    return [x * S for x in xs]


def fx(two_theta):
    x0, _, x1, _ = PLOT
    return x0 + (two_theta - TWO_THETA[0]) / (TWO_THETA[1] - TWO_THETA[0]) * (x1 - x0)


def reflections(a=6.36, wavelength=1.5406):
    """Return [(label, two_theta, intensity)] for Pm-3m FAPbI3, strongest scaled to 1.

    FA (25 e) sits at the origin, Pb at the body centre and I on the face centres. Form
    factors fall off with a single Gaussian, which is rough but keeps the ratios honest.
    """
    groups = {}
    for h, k, l in itertools.product(range(-5, 6), repeat=3):
        n = h * h + k * k + l * l
        if not n:
            continue
        d = a / math.sqrt(n)
        s = 1 / (2 * d)
        if wavelength * s >= 1:
            continue
        two_theta = 2 * math.degrees(math.asin(wavelength * s))
        if not TWO_THETA[0] < two_theta < TWO_THETA[1]:
            continue
        form = math.exp(-6 * s * s)
        f = 25 * form + 82 * form * (-1) ** (h + k + l)
        f += 53 * form * ((-1) ** (h + k) + (-1) ** (k + l) + (-1) ** (h + l))
        theta = math.radians(two_theta / 2)
        lp = (1 + math.cos(2 * theta) ** 2) / (math.sin(theta) ** 2 * math.cos(theta))
        entry = groups.setdefault(n, {"two_theta": two_theta, "i": 0.0, "families": set()})
        entry["i"] += f * f * lp * math.exp(-6 * s * s)  # the last factor is thermal motion
        entry["families"].add(tuple(sorted(map(abs, (h, k, l)), reverse=True)))
    peak = max(e["i"] for e in groups.values())
    out = []
    for n in sorted(groups):
        e = groups[n]
        names = sorted(("".join(map(str, fam)) for fam in e["families"]), reverse=True)
        out.append(("/".join(names), e["two_theta"], e["i"] / peak))
    return out


def trace(peaks):
    """Return [(x, y)] in px: pseudo-Voigt peaks on a low background, with counting noise."""
    x0, y0, x1, y1 = PLOT
    rng = random.Random(7)
    fwhm = 0.17
    out = []
    for px in range(int(x0), int(x1) + 1):
        t = TWO_THETA[0] + (px - x0) / (x1 - x0) * (TWO_THETA[1] - TWO_THETA[0])
        v = 0.018 + 0.022 * math.exp(-(((t - 24) / 8) ** 2))
        for _, c, h in peaks:
            d = (t - c) / (fwhm / 2)
            v += h * 0.9 * (0.5 / (1 + d * d) + 0.5 * math.exp(-math.log(2) * d * d))
        v += rng.gauss(0, 0.0035 + 0.006 * math.sqrt(max(v, 0)))
        out.append((px, y1 - max(0.0, v) * (y1 - y0)))
    return out


def title_dots():
    """Yield (x, y, lit) for every cell of the title."""
    col = 0
    for ch in TITLE:
        for r, row in enumerate(GLYPHS[ch].split()):
            for c, cell in enumerate(row):
                yield TITLE_XY[0] + (col + c) * PITCH, TITLE_XY[1] + r * PITCH, cell == "1"
        col += 6


def blank_sheet(t):
    """The parts that never move: paper or graticule, plus the printed 2-theta axis."""
    img = Image.new("RGB", (W * S, H * S), t["bg"])
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = PLOT
    if t["name"] == "light":
        top, bottom = 30, H - 30
        for x in range(0, W + 1, 10):
            d.line(scaled(x, top, x, bottom), fill=t["major"] if x % 50 == 0 else t["minor"], width=S)
        for y in range(top, bottom + 1, 10):
            d.line(scaled(0, y, W, y), fill=t["major"] if (y - top) % 50 == 0 else t["minor"], width=S)
        for x in range(25, W, 50):
            for y in (15, H - 15):
                d.ellipse(scaled(x - 5, y - 5, x + 5, y + 5), fill=(255, 255, 255), outline=t["major"], width=S)
    else:
        for i in range(13):
            x = x0 + (x1 - x0) * i / 12
            d.line(scaled(x, y0, x, y1), fill=t["minor"], width=S)
        for i in range(5):
            y = y0 + (y1 - y0) * i / 4
            d.line(scaled(x0, y, x1, y), fill=t["minor"], width=S)
    d.line(scaled(x0, y1, x1, y1), fill=t["text"] if t["name"] == "light" else t["major"], width=S)
    for deg in range(int(TWO_THETA[0]), int(TWO_THETA[1]) + 1):
        tick = 8 if deg % 5 == 0 else 4
        d.line(scaled(fx(deg), y1, fx(deg), y1 + tick), fill=t["text"] if t["name"] == "light" else t["major"], width=S)
        if deg % 10 == 0:
            label = str(deg)
            d.text(scaled(fx(deg) - d.textlength(label, font=font(13)) / S / 2, y1 + 12), label, font=font(13), fill=t["text"])
    label = "2θ (deg)"
    d.text(scaled(fx(35) - d.textlength(label, font=font(13)) / S / 2, y1 + 12), label, font=font(13), fill=t["text"])
    if t["off_dot"]:
        for x, y, _ in title_dots():
            d.ellipse(scaled(x - 3.8, y - 3.8, x + 3.8, y + 3.8), fill=t["off_dot"])
    return img


def ink_layers(t, peaks):
    """Masks for what the beam or pen lays down: {color: L mask}."""
    size = (W * S, H * S)
    rng = random.Random(21)
    title = Image.new("L", size, 0)
    d = ImageDraw.Draw(title)
    for x, y, lit in title_dots():
        if not lit:
            continue
        if t["name"] == "light":
            # A worn ribbon: dots land slightly off grid and not all equally dark.
            x += rng.uniform(-0.35, 0.35)
            y += rng.uniform(-0.35, 0.35)
            d.ellipse(scaled(x - 3.7, y - 3.7, x + 3.7, y + 3.7), fill=rng.randint(205, 255))
        else:
            d.ellipse(scaled(x - 4.2, y - 4.2, x + 4.2, y + 4.2), fill=255)

    line = Image.new("L", size, 0)
    points = trace(peaks)
    ImageDraw.Draw(line).line([tuple(scaled(x, y)) for x, y in points], fill=255, width=int(1.6 * S), joint="curve")

    labels = Image.new("L", size, 0)
    d = ImageDraw.Draw(labels)
    for name, c, h in peaks:
        px = fx(c)
        if h < 0.02:
            continue
        top = min(y for x, y in points if abs(x - px) < 4)
        width = d.textlength(name, font=font(13, bold=True)) / S
        d.text(scaled(px - width / 2, top - 21), name, font=font(13, bold=True), fill=255)

    header = Image.new("L", size, 0)
    d = ImageDraw.Draw(header)
    for i, row in enumerate(HEADER):
        width = d.textlength(row, font=font(14)) / S
        d.text(scaled(PLOT[2] - width, 62 + i * 25), row, font=font(14), fill=255)
    return [(t["title"], title, 7, 0.5), (t["trace"], line, 4, 0.55), (t["label"], labels, 0, 0), (t["text"], header, 0, 0)]


def apply_ink(base, layers, t, dx=0, color_override=None):
    img = base.copy()
    for color, mask, radius, strength in layers:
        m = mask if not dx else ImageChops.offset(mask, -dx * S, 0)
        if dx:
            # offset wraps around; blank whatever came back in on the right.
            ImageDraw.Draw(m).rectangle(((W - dx) * S, 0, W * S, H * S), fill=0)
        if t["name"] == "dark" and radius:
            glow = m.filter(ImageFilter.GaussianBlur(radius * S)).point(lambda v: min(255, int(v * strength)))
            img.paste(color_override or color, (0, 0), glow)
        img.paste(color_override or color, (0, 0), m)
    return img


def down(img):
    return img.resize((W, H), Image.LANCZOS)


def beam_strip(t):
    half = 16
    strip = Image.new("RGB", (half * 2 + 1, H), (0, 0, 0))
    d = ImageDraw.Draw(strip)
    for dx in range(-half, half + 1):
        k = 0.8 if dx == 0 else (1 - abs(dx) / half) ** 2 * 0.2
        d.line([(dx + half, 0), (dx + half, H)], fill=tuple(int(c * k) for c in t["hot"]))
    return strip


def frame_at(bx, t, off, done, hot, strip, tips):
    img = off.copy()
    if bx > 0:
        img.paste(done.crop((0, 0, bx, H)), (0, 0))
    if t["name"] == "dark":
        if bx > 0:
            trail = min(bx, 150)
            ramp = Image.linear_gradient("L").rotate(90, expand=True).resize((trail, H))
            img.paste(hot.crop((bx - trail, 0, bx, H)), (bx - trail, 0), ramp)
        half = strip.width // 2
        left, right = max(0, bx - half), min(W, bx + half + 1)
        if right > left:
            part = strip.crop((left - (bx - half), 0, right - (bx - half), H))
            img.paste(ImageChops.add(img.crop((left, 0, right, H)), part), (left, 0))
    else:
        # The chart recorder's carriage: a thin rail with the pen riding on the trace.
        d = ImageDraw.Draw(img)
        if 0 <= bx < W:
            d.line([(bx, 30), (bx, H - 30)], fill=(120, 112, 104), width=1)
            y = tips.get(bx)
            if y is not None:
                d.polygon([(bx, y), (bx - 5, y - 11), (bx + 5, y - 11)], fill=(200, 50, 26))
    return img


def build(t, path):
    peaks = reflections()
    points = dict(trace(peaks))
    tips = {int(x): y for x, y in points.items()}
    layers = ink_layers(t, peaks)
    blank = blank_sheet(t)
    off = down(blank)
    done = down(apply_ink(blank, layers, t))
    hot = down(apply_ink(blank, layers, t, color_override=t["hot"])) if t["name"] == "dark" else done
    strip = beam_strip(t)

    # One palette for every frame, so colours can't flicker between frames.
    sample = Image.new("RGB", (W, H * 3))
    for i, im in enumerate((off, done, hot)):
        sample.paste(im, (0, i * H))
    palette = sample.quantize(colors=112, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)

    frames, delays = [], []

    def push(img, ms):
        frames.append(img.quantize(palette=palette, dither=Image.Dither.NONE))
        delays.append(ms)

    # Frame 0 is what paused or reduced-motion viewers see, so it must be the finished sheet.
    push(done, 5200)
    if t["name"] == "dark":
        for i in range(1, 7):
            push(Image.blend(done, off, i / 6), 60)
    else:
        # The sheet feeds out. Moving by whole grid squares keeps the printed grid still.
        for dx in (50, 100, 200, 350, 550, 800, 1050, 1250):
            push(down(apply_ink(blank, layers, t, dx=dx)), 55)
    push(off, 350)
    sweep = 72
    for i in range(sweep + 1):
        push(frame_at(round(W * i / sweep), t, off, done, hot, strip, tips), 40)

    frames[0].save(path, save_all=True, append_images=frames[1:], duration=delays, loop=0, disposal=1)


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for name, t in (("dark", DARK), ("light", LIGHT)):
        build(t, out / f"hero-{name}.gif")
    for name, c, h in reflections():
        print(f"{name:>8}  2θ={c:6.2f}  I={h:5.3f}")


if __name__ == "__main__":
    main(sys.argv[1])
