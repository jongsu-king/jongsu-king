#!/usr/bin/env python3
"""Generate assets/fig-*-{dark,light}.svg from data files in the project repositories.

Each panel reads a file that ships in one of the repos, and the README caption names
it. Run by hand when those files change. Panel e needs Pillow, to cut the map out of
SUYA's screenshot.

Usage: make_figures.py OUTPUT_DIR CACHE_DIR
"""
import base64
import collections
import csv
import io
import json
import math
import sys
import urllib.request
from pathlib import Path

from figstyle import THEMES, Axes, document, path, ramp_color, text

RAW = "https://raw.githubusercontent.com/jongsu-king/"
SOURCES = {
    "am15.csv": "physiscore/main/scripts/EQE/astm_g173_global.csv",
    "xrd.csv": "xrd-analyzer/main/examples/synthetic/synthetic_nano_fcc.csv",
    "xrd_truth.json": "xrd-analyzer/main/examples/synthetic/synthetic_nano_fcc_truth.json",
    "nmr.jdx": "nmr-analyzer/main/education/datasets/01-ethyl-acetate.jdx",
    "opv.csv": "opv-db-based-on-literature/main/data/opv_devices.csv",
    "clubs.json": "SwingLab/main/SwingLab/Resources/Catalog/equipment-catalog.json",
    "suya.png": "SUYA/main/docs/images/en-1-water.png",
}
W, H = 360, 300
BOX = (50, 36, 336, 246)
BANDGAP_EV = 1.48  # alpha-FAPbI3, the phase in the hero pattern


def heading(t, letter, title, right=""):
    out = text(2, 18, letter, t["ink"], 16, weight=700) + text(20, 18, title, t["ink"], 14.5)
    if right:
        out += text(BOX[2], 18, right, t["sub"], 12.5, "end")
    return out


def thin(points, keep_every):
    return points[::keep_every] + points[-1:]


def panel_sun(t, cache):
    rows = [(float(r["wavelength_nm"]), float(r["global_tilt_W_m2_nm"])) for r in csv.DictReader(open(cache / "am15.csv"))]
    total = sum((b[0] - a[0]) * (a[1] + b[1]) / 2 for a, b in zip(rows, rows[1:]))
    edge = 1239.84 / BANDGAP_EV
    ax = Axes(t, BOX, (280, 2500), (0, 1.75))
    shown = [(ax.x(w), ax.y(i)) for w, i in rows if w <= 2500]
    above = [(ax.x(w), ax.y(i)) for w, i in rows if w <= edge]
    area = above + [(above[-1][0], ax.y(0)), (above[0][0], ax.y(0))]
    body = heading(t, "a", "AM1.5G spectrum", f"∫ = {total:.0f} W m⁻²")
    body += path(area, "none", 0, t["accent"], 'fill-opacity=".28"')
    body += path(thin(shown, 2), t["ink"], 1)
    body += ax.draw((500, 1000, 1500, 2000, 2500), (0, 0.5, 1.0, 1.5), "Wavelength (nm)", "W m⁻² nm⁻¹")
    body += f'<path d="M{ax.x(edge):.1f} {ax.y(1.72):.1f} V{ax.y(0):.1f}" stroke="{t["accent"]}" stroke-dasharray="3 3"/>'
    body += text(ax.x(edge) + 6, ax.y(1.62), f"{edge:.0f} nm", t["accent"], 12.5, weight=600)
    body += text(ax.x(edge) + 6, ax.y(1.62) + 15, f"Eg = {BANDGAP_EV} eV", t["sub"], 12.5)
    return body, "AM1.5G solar spectrum with the part above a 1.48 eV band gap shaded"


def panel_xrd(t, cache):
    rows = []
    for row in csv.reader(line for line in open(cache / "xrd.csv", encoding="utf-8") if not line.startswith("#")):
        try:
            rows.append((float(row[0]), float(row[1])))
        except (ValueError, IndexError):
            continue
    truth = json.load(open(cache / "xrd_truth.json", encoding="utf-8"))
    top = max(c for _, c in rows)
    ax = Axes(t, BOX, (20, 105), (0, top * 1.14))
    body = heading(t, "b", "XRD, synthetic nano-fcc")
    body += path(thin([(ax.x(a), ax.y(c)) for a, c in rows], 2), t["ink"], 1)
    body += ax.draw((20, 40, 60, 80, 100), (0, 2000, 4000), "2θ (deg)", "Counts")
    placed = []
    for p in truth["peaks"]:
        px = ax.x(p["two_theta_deg"])
        body += f'<path d="M{px:.1f} {ax.y(0):.1f} v-7" stroke="{t["accent"]}" stroke-width="1.6"/>'
        local = max(c for a, c in rows if abs(a - p["two_theta_deg"]) < 0.6)
        y = ax.y(local) - 6
        # Close neighbours (311 and 222) stack instead of overprinting.
        if any(abs(px - qx) < 26 and abs(y - qy) < 14 for qx, qy in placed):
            y -= 14
        placed.append((px, y))
        body += text(px, y, p["hkl"], t["accent"], 12, "middle", weight=600)
    return body, "Synthetic nanocrystalline fcc diffraction pattern with indexed peaks"


def read_jcamp(file):
    header, ys, reading = {}, [], False
    for line in open(file, encoding="utf-8", errors="replace"):
        if line.startswith("##"):
            key, _, value = line[2:].partition("=")
            header[key.strip()] = value.strip()
            reading = key.strip() == "XYDATA"
            continue
        if reading:
            ys.extend(float(v) for v in line.split()[1:])
    first, last = float(header["FIRSTX"]), float(header["LASTX"])
    factor = float(header["YFACTOR"])
    step = (last - first) / (len(ys) - 1)
    return [(first + i * step, y * factor) for i, y in enumerate(ys)]


def panel_nmr(t, cache):
    rows = read_jcamp(cache / "nmr.jdx")
    window = [(p, v) for p, v in rows if 0.4 <= p <= 5.0]
    top = max(v for _, v in window)
    ax = Axes(t, BOX, (5.0, 0.4), (-0.03 * top, top * 1.12))
    body = heading(t, "c", "¹H NMR, ethyl acetate", "400 MHz")
    body += path([(ax.x(p), ax.y(v)) for p, v in window], t["ink"], 0.9)
    body += ax.draw((5, 4, 3, 2, 1), (), "Chemical shift (ppm)")

    def peak_height(lo, hi):
        return max(v for p, v in window if lo <= p <= hi)

    assignments = [("OCH₂", 3.95, 4.30), ("CH₃CO", 1.9, 2.2), ("CH₃", 1.1, 1.45)]
    for name, lo, hi in assignments:
        mid = (lo + hi) / 2
        body += text(ax.x(mid), ax.y(peak_height(lo, hi)) - 6, name, t["sub"], 12.5, "middle")

    # Inset: the quartet, blown up so the 1:3:3:1 pattern can actually be read.
    lo, hi = 3.98, 4.26
    region = [(p, v) for p, v in window if lo <= p <= hi]
    tall = max(v for _, v in region)
    ix0, ix1, iy0, iy1 = BOX[0] + 66, BOX[0] + 158, BOX[1] + 22, BOX[1] + 92
    inset = [(ix0 + (hi - p) / (hi - lo) * (ix1 - ix0), iy1 - max(v, 0) / tall * (iy1 - iy0)) for p, v in region]
    body += path(inset, t["accent"], 1.1)
    body += f'<path d="M{ix0} {iy1} H{ix1}" stroke="{t["axis"]}"/>'
    body += text((ix0 + ix1) / 2, iy1 + 15, f"×{top / tall:.1f}", t["accent"], 12, "middle", weight=600)
    return body, "Proton NMR of ethyl acetate with an inset of the OCH2 quartet"


def load_opv(cache):
    cells = collections.Counter()
    n = 0
    nx, ny = 46, 38
    jmax, vmin, vmax = 30.0, 0.2, 1.2
    for row in csv.DictReader(open(cache / "opv.csv", encoding="utf-8", newline="")):
        try:
            v, j = float(row["voc"]), float(row["jsc"])
        except ValueError:
            continue
        if 0 < j <= jmax and vmin <= v <= vmax:
            n += 1
            cells[(min(int(j / jmax * nx), nx - 1), min(int((v - vmin) / (vmax - vmin) * ny), ny - 1))] += 1
    return cells, n, (nx, ny, jmax, vmin, vmax)


def panel_opv(t, opv):
    cells, n, (nx, ny, jmax, vmin, vmax) = opv
    ax = Axes(t, BOX, (0, jmax), (vmin, vmax))
    body = heading(t, "d", "OPV-DB, Voc against Jsc", f"n = {n:,}")
    peak = math.log1p(max(cells.values()))
    cw, ch = (BOX[2] - BOX[0]) / nx, (BOX[3] - BOX[1]) / ny
    for (i, k), c in cells.items():
        fill = ramp_color(t, 0.16 + 0.84 * math.log1p(c) / peak)
        body += f'<rect x="{BOX[0] + i * cw:.1f}" y="{BOX[3] - (k + 1) * ch:.1f}" width="{cw + 0.3:.1f}" height="{ch + 0.3:.1f}" fill="{fill}"/>'
    for pce in (5, 10, 15, 20):
        line = [(ax.x(j), ax.y(pce / (j * 0.7))) for j in (x / 2 for x in range(2, 61)) if vmin <= pce / (j * 0.7) <= vmax]
        body += path(line, t["ink"], 0.9, extra='stroke-dasharray="3 3"')
        x, y = line[-1]
        body += text(x - 2, y - 5, f"{pce}%", t["ink"], 12, "end", weight=600)
    body += ax.draw((0, 10, 20, 30), (0.2, 0.4, 0.6, 0.8, 1.0, 1.2), "Jsc (mA cm⁻²)", "Voc (V)")
    return body, f"Two-dimensional histogram of open-circuit voltage against short-circuit current for {n} organic solar cells"


def cut_suya_map(cache):
    """Cut the disc and colour bar out of SUYA's screenshot; return (jpeg data URI, bar stops)."""
    from PIL import Image

    img = Image.open(cache / "suya.png").convert("RGB")
    w, h = img.size
    def saturated(x, y):
        r, g, b = img.getpixel((x, y))
        return max(r, g, b) - min(r, g, b) > 40
    region_right = int(w * 0.5)
    xs, ys = [], []
    for y in range(int(h * 0.08), int(h * 0.88)):
        for x in range(0, region_right, 2):
            if saturated(x, y):
                xs.append(x)
                ys.append(y)
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    side = max(x1 - x0, y1 - y0)
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    crop = img.crop((cx - side // 2, cy - side // 2, cx + side // 2 + 1, cy + side // 2 + 1))
    buf = io.BytesIO()
    crop.save(buf, "JPEG", quality=88, subsampling=0)

    for y in range(y1 + 4, h):
        run = [x for x in range(0, region_right) if saturated(x, y)]
        if len(run) > region_right * 0.5:
            row = y + 2
            bx0, bx1 = run[0], run[-1]
            break
    stops = [img.getpixel((bx0 + (bx1 - bx0) * i // 15, row)) for i in range(16)]
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode(), stops


def panel_suya(t, suya):
    uri, stops = suya
    cx, cy, r = 169, 134, 106
    body = heading(t, "e", "SUYA, sea surface temperature")
    body += f'<clipPath id="disc"><circle cx="{cx}" cy="{cy}" r="{r - 0.5}"/></clipPath>'
    body += f'<image href="{uri}" x="{cx - r}" y="{cy - r}" width="{2 * r}" height="{2 * r}" clip-path="url(#disc)"/>'
    gradient = "".join(f'<stop offset="{i / 15:.3f}" stop-color="#%02x%02x%02x"/>' % c for i, c in enumerate(stops))
    bx0, bx1, by = 59, 279, 256
    body += f'<linearGradient id="bar">{gradient}</linearGradient><rect x="{bx0}" y="{by}" width="{bx1 - bx0}" height="8" fill="url(#bar)"/>'
    for frac, label in ((0, "-2"), (0.5, "6.5"), (1, "15 °C")):
        x = bx0 + (bx1 - bx0) * frac
        body += f'<path d="M{x} {by + 8} v4" stroke="{t["axis"]}"/>' + text(x, by + 26, label, t["sub"], 12.5, "middle")
    return body, "South polar map of sea surface temperature from the SUYA desktop app"


def panel_clubs(t, cache):
    catalog = json.load(open(cache / "clubs.json", encoding="utf-8"))
    names = {b["id"]: b["name"] for b in catalog["brands"]}
    clubs = catalog["clubs"]
    by_brand = collections.Counter(c["brandID"] for c in clubs)
    top = [b for b, _ in by_brand.most_common(9)]
    counts = collections.Counter((c["brandID"], c["releaseYear"]) for c in clubs)
    first, last = min(c["releaseYear"] for c in clubs), max(c["releaseYear"] for c in clubs)
    box = (92, 36, BOX[2], 246)
    cols = last - first + 1
    cw, ch = (box[2] - box[0]) / cols, (box[3] - box[1]) / len(top)
    peak = max(counts[(b, y)] for b in top for y in range(first, last + 1))
    ax = Axes(t, box, (first - 0.5, last + 0.5), (0, 1))
    body = heading(t, "f", "SwingLab, club catalog", f"{len(clubs):,} models")
    for r, brand in enumerate(top):
        y = box[1] + r * ch
        body += text(box[0] - 7, y + ch / 2 + 4, names[brand], t["sub"], 12, "end")
        for year in range(first, last + 1):
            c = counts[(brand, year)]
            if c:
                fill = ramp_color(t, 0.2 + 0.8 * c / peak)
                body += f'<rect x="{box[0] + (year - first) * cw + 0.6:.1f}" y="{y + 0.6:.1f}" width="{cw - 1.2:.1f}" height="{ch - 1.2:.1f}" fill="{fill}"/>'
    body += ax.draw([y for y in (2000, 2010, 2020) if first <= y <= last], (), "Release year")
    return body, f"Heat map of {len(clubs)} golf club models by brand and release year"


def main(out, cache):
    out, cache = Path(out), Path(cache)
    out.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    for name, source in SOURCES.items():
        if not (cache / name).exists():
            urllib.request.urlretrieve(RAW + source, cache / name)
    opv = load_opv(cache)
    suya = cut_suya_map(cache)
    panels = {
        "a": lambda t: panel_sun(t, cache),
        "b": lambda t: panel_xrd(t, cache),
        "c": lambda t: panel_nmr(t, cache),
        "d": lambda t: panel_opv(t, opv),
        "e": lambda t: panel_suya(t, suya),
        "f": lambda t: panel_clubs(t, cache),
    }
    for letter, build in panels.items():
        for mode, theme in THEMES.items():
            body, label = build(theme)
            (out / f"fig-{letter}-{mode}.svg").write_text(document(W, H, theme, body, label), encoding="utf-8")
    print("opv devices plotted:", opv[1])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
