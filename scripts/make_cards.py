#!/usr/bin/env python3
"""Generate assets/card-*.svg: one animated instrument screen per project.

Curve shapes are illustrative, so they carry no measured values. The only numbers on
the cards are facts copied from each project's README (tests, record counts, recipe).

Usage: make_cards.py OUTPUT_DIR   (standard library only)
"""
import math
import random
import sys
from pathlib import Path
from xml.sax.saxutils import escape

BG = "#0C0B08"
GRID = "#201C12"
MAJOR = "#2E2818"
AMBER = "#FFB000"
HOT = "#FFECBE"
DIM = "#A88034"
TEAL = "#4FD1C5"
TEXT = "#E8DCC0"

CYCLE = "11s"
SWEEP_END = "32%"


def style(sweep_px):
    return f"""
text{{font-family:ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace}}
.kick{{font-size:13px;fill:{DIM};letter-spacing:1.4px}}
.name{{font-weight:700;fill:{AMBER}}}
.desc{{font-size:15px;fill:{TEXT}}}
.tag{{font-size:12.5px;fill:{DIM};letter-spacing:.6px}}
.lab{{font-size:13px;font-weight:700;fill:{AMBER}}}
.val{{font-size:15px;fill:{TEXT}}}
.ax{{font-size:11.5px;fill:{DIM}}}
.trace{{fill:none;stroke:{AMBER};stroke-width:2;stroke-linejoin:round;stroke-linecap:round}}
.ghost{{fill:none;stroke:{AMBER};stroke-width:5;opacity:.4;filter:url(#glow)}}
.teal{{fill:none;stroke:{TEAL};stroke-width:1.2}}
.dimline{{fill:none;stroke:{DIM};stroke-width:1.2}}
.cover{{fill:{BG};transform:translateX({sweep_px}px);animation:sweep {CYCLE} linear infinite}}
.beam{{stroke:{HOT};stroke-width:1.6;opacity:0;animation:beam {CYCLE} linear infinite}}
.spin{{animation:spin 7s linear infinite}}
.pulse{{animation:pulse 2.4s ease-in-out infinite}}
@keyframes sweep{{0%{{transform:translateX(0)}}{SWEEP_END},100%{{transform:translateX({sweep_px}px)}}}}
@keyframes beam{{0%{{transform:translateX(0);opacity:1}}{SWEEP_END}{{transform:translateX({sweep_px}px);opacity:1}}32.01%,100%{{transform:translateX({sweep_px}px);opacity:0}}}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
@keyframes pulse{{50%{{opacity:.25}}}}
@media (prefers-reduced-motion:reduce){{.cover,.beam,.spin,.pulse{{animation:none}}}}
"""


def poly(points):
    return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in points)


def glow_trace(points):
    d = poly(points)
    return f'<path class="ghost" d="{d}"/><path class="trace" d="{d}"/>'


def label(x, y, text, cls="lab", anchor="middle", extra=""):
    return f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}" text-anchor="{anchor}" {extra}>{escape(text)}</text>'


def card(path, *, kick, title, right, desc, tags, body, title_size=26, w=600, h=340, plot=(24, 70, 576, 232)):
    x0, y0, x1, y1 = plot
    pw, ph = x1 - x0, y1 - y0
    grid = []
    for i in range(1, 12):
        x = x0 + pw * i / 12
        grid.append(f'<path d="M{x:.1f} {y0} V{y1}"/>')
    for i in range(1, 4):
        y = y0 + ph * i / 4
        grid.append(f'<path d="M{x0} {y:.1f} H{x1}"/>')

    text_y = y1 + 30
    lines = "".join(label(24, text_y + i * 21, s, "desc", "start") for i, s in enumerate(desc))
    tag_y = text_y + len(desc) * 21 + 8
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{escape(title)}: {escape(' '.join(desc))}">
<style>{style(pw)}</style>
<defs><filter id="glow" x="-5%" y="-20%" width="110%" height="140%"><feGaussianBlur stdDeviation="3"/></filter>
<clipPath id="plot"><rect x="{x0}" y="{y0}" width="{pw}" height="{ph}"/></clipPath></defs>
<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="14" fill="{BG}" stroke="{MAJOR}" stroke-width="2"/>
{label(24, 30, kick, "kick", "start")}{label(w - 24, 30, right, "kick", "end")}
<text x="24" y="58" class="name" font-size="{title_size}">{escape(title)}</text>
<g clip-path="url(#plot)">
<g>{body}</g>
<rect class="cover" x="{x0}" y="{y0}" width="{pw}" height="{ph}"/>
<g fill="none" stroke="{GRID}">{''.join(grid)}</g>
<path class="beam" d="M{x0} {y0} V{y1}"/>
</g>
<rect x="{x0}" y="{y0}" width="{pw}" height="{ph}" fill="none" stroke="{MAJOR}"/>
{lines}{label(24, tag_y, tags, "tag", "start")}
</svg>
"""
    Path(path).write_text(svg, encoding="utf-8")


def physiscore():
    x0, x1 = 60, 556
    zero, top = 188, 90
    n = 0.045
    vmin, vmax = -0.06, 1.1
    fx = lambda v: x0 + (v - vmin) / (vmax - vmin) * (x1 - x0)
    fy = lambda j: zero - j * (zero - top)
    light = lambda v: 1 - (math.exp(v / n) - 1) / (math.exp(1 / n) - 1)
    volts = [vmin + (vmax - vmin) * i / 300 for i in range(301)]
    curve = [(fx(v), fy(light(v))) for v in volts if light(v) > -0.5]
    dark = [(fx(v), fy(light(v) - 1)) for v in volts if light(v) - 1 > -0.5]
    vmp = max((v for v in volts if v > 0), key=lambda v: v * light(v))
    mx, my = fx(vmp), fy(light(vmp))
    return (
        f'<path d="M{x0} {zero} H{x1}" class="dimline"/><path d="M{fx(0):.1f} 76 V226" class="dimline"/>'
        f'<rect x="{fx(0):.1f}" y="{my:.1f}" width="{mx - fx(0):.1f}" height="{zero - my:.1f}" fill="{TEAL}" fill-opacity=".1" stroke="{TEAL}" stroke-dasharray="4 4"/>'
        f'<path d="{poly(dark)}" class="dimline" stroke-dasharray="3 4"/>'
        + glow_trace(curve)
        + f'<circle cx="{mx:.1f}" cy="{my:.1f}" r="4.5" fill="{HOT}"/>'
        + label(mx + 10, my - 8, "MPP", anchor="start")
        + label(fx(0) + 8, top - 6, "Jsc", anchor="start")
        + label(fx(1), zero + 18, "Voc")
        + label(fx(0) + (mx - fx(0)) / 2, zero - 12, "FF", extra=f'style="fill:{TEAL}"')
        + label(x1, zero - 8, "V", "ax", "end")
        + label(fx(0) - 8, 88, "J", "ax", "end")
    )


def xrd():
    x0, x1 = 34, 566
    base, top = 200, 92
    peaks = [("(111)", 38.2, 1.0), ("(200)", 44.4, 0.46), ("(220)", 64.6, 0.3), ("(311)", 77.5, 0.34), ("(222)", 81.7, 0.1), ("(400)", 98.1, 0.07)]
    fx = lambda t: x0 + (t - 20) / 85 * (x1 - x0)
    rng = random.Random(3)
    trace, resid = [], []
    for i in range(int(x1 - x0) * 2 + 1):
        t = 20 + i / (2 * (x1 - x0)) * 85
        v = 0.03 + 0.13 * math.exp(-(((t - 26) / 5.5) ** 2))
        near = 0.0
        for _, c, h in peaks:
            d = (t - c) / 0.3
            v += h * 0.8 * (0.6 / (1 + d * d) + 0.4 * math.exp(-0.5 * d * d))
            near = max(near, math.exp(-(((t - c) / 1.2) ** 2)))
        v += rng.gauss(0, 0.005)
        trace.append((fx(t), base - v * (base - top)))
        resid.append((fx(t), 218 + rng.gauss(0, 0.8 + 4.5 * near)))
    labels = "".join(
        label(fx(c), base - (h * 0.8 + 0.06) * (base - top) - (19 if name == "(222)" else 6), name)
        for name, c, h in peaks
    )
    return f'<path d="{poly(resid)}" class="teal"/>' + glow_trace(trace) + labels + label(562, 184, "2θ", "ax", "end")


def nmr():
    x0, x1 = 34, 566
    base, top = 206, 98
    groups = [("s", 7.25, [1.0], 0.95), ("d", 6.1, [1, 1], 0.5), ("t", 4.15, [1, 2, 1], 0.32), ("q", 2.45, [1, 3, 3, 1], 0.2), ("s", 1.2, [1.0], 0.8)]
    fx = lambda p: x0 + (8.2 - p) / 7.4 * (x1 - x0)
    lines = []
    for _, c, weights, h in groups:
        n = len(weights)
        for i, w in enumerate(weights):
            lines.append((c + (i - (n - 1) / 2) * 0.1, h * w))
    trace, integral = [], []
    area = 0.0
    total = sum(h for _, h in lines)
    for i in range(int(x1 - x0) * 3 + 1):
        p = 8.2 - i / (3 * (x1 - x0)) * 7.4
        v = sum(h / (1 + ((p - c) / 0.012) ** 2) for c, h in lines)
        area += v
        trace.append((fx(p), base - min(v, 1.02) * (base - top)))
        integral.append((fx(p), area))
    k = area or 1
    integral = [(x, 212 - a / k * 128) for x, a in integral]
    labels = "".join(label(fx(c), base - max(w for w in ws) * h * (base - top) - 8, name) for name, c, ws, h in groups)
    ticks = "".join(label(fx(p), 226, str(p), "ax") for p in range(8, 0, -1))
    return f'<path d="M{x0} {base} H{x1}" class="dimline"/><path d="{poly(integral)}" class="teal"/>' + glow_trace(trace) + labels + ticks


def suya():
    cx, cy, r = 118, 151, 76
    rings = "".join(f'<circle cx="{cx}" cy="{cy}" r="{r * f:.1f}" fill="{AMBER}" fill-opacity="{o}"/>' for f, o in [(1, 0.34), (0.86, 0.22), (0.72, 0.12), (0.58, 0.05)])
    grid = "".join(f'<circle cx="{cx}" cy="{cy}" r="{r * f:.1f}" fill="none" stroke="{MAJOR}"/>' for f in (0.33, 0.66, 1))
    for a in range(0, 180, 30):
        dx, dy = r * math.cos(math.radians(a)), r * math.sin(math.radians(a))
        grid += f'<path d="M{cx - dx:.1f} {cy - dy:.1f} L{cx + dx:.1f} {cy + dy:.1f}" stroke="{MAJOR}"/>'
    land = []
    for i in range(96):
        th = i / 96 * 2 * math.pi  # 0 at the top, clockwise, like the app's polar map
        rho = 0.36 + 0.07 * math.sin(2 * th + 1) + 0.04 * math.sin(3 * th + 0.5)
        rho += 0.26 * math.exp(-(((th - 5.3) / 0.14) ** 2))  # the Antarctic Peninsula
        land.append((cx + r * rho * math.sin(th), cy - r * rho * math.cos(th)))
    rng = random.Random(5)
    floats = ""
    for _ in range(46):
        th, rho = rng.uniform(0, 2 * math.pi), rng.uniform(0.56, 0.97)
        floats += f'<circle cx="{cx + r * rho * math.sin(th):.1f}" cy="{cy - r * rho * math.cos(th):.1f}" r="1.5" fill="{HOT}"/>'
    wedge = f'<g class="spin" style="transform-origin:{cx}px {cy}px"><path d="M{cx} {cy} L{cx} {cy - r} A{r} {r} 0 0 1 {cx + r * math.sin(0.7):.1f} {cy - r * math.cos(0.7):.1f} Z" fill="{TEAL}" fill-opacity=".28"/><path d="M{cx} {cy} L{cx} {cy - r}" stroke="{TEAL}" stroke-width="1.6"/></g>'

    sources = ["NOAA OISST", "GFS", "METAR", "HYCOM", "Argo", "SMOS/SMAP", "GOSUD", "WOA23", "ECMWF"]
    readout = label(232, 96, "SOURCES", "kick", "start")
    for i, name in enumerate(sources):
        x = 232 + (i % 3) * 112
        y = 128 + (i // 3) * 30
        readout += f'<circle class="pulse" style="animation-delay:{i * 0.27:.2f}s" cx="{x + 4}" cy="{y - 4}" r="3.2" fill="{TEAL}"/>' + label(x + 14, y, name, "ax", "start", f'style="font-size:13px;fill:{TEXT}"')
    readout += label(232, 218, "T · S · AIR → SQLITE + MONTHLY EXCEL", "kick", "start")
    return rings + grid + f'<path d="{poly(land)} Z" fill="#D9D2BE"/>' + floats + wedge + readout


def calculator():
    cx, cy = 118, 150
    def p(x, y, z):
        return cx + (x - z) * 38, cy + (x + z) * 19 - y * 42
    corners = [(a, b, c) for a in (-1, 1) for b in (-1, 1) for c in (-1, 1)]
    edges = ""
    for i, u in enumerate(corners):
        for v in corners[i + 1 :]:
            if sum(a != b for a, b in zip(u, v)) == 1:
                edges += f'<path d="M{p(*u)[0]:.1f} {p(*u)[1]:.1f} L{p(*v)[0]:.1f} {p(*v)[1]:.1f}" stroke="{DIM}" stroke-width="1.2"/>'
    faces = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
    octa = ""
    for i, u in enumerate(faces):
        for v in faces[i + 1 :]:
            if u != tuple(-a for a in v):
                octa += f'<path d="M{p(*u)[0]:.1f} {p(*u)[1]:.1f} L{p(*v)[0]:.1f} {p(*v)[1]:.1f}" stroke="{AMBER}" stroke-opacity=".75"/>'
    atoms = "".join(f'<circle cx="{p(*c)[0]:.1f}" cy="{p(*c)[1]:.1f}" r="6" fill="{TEAL}"/>' for c in corners)
    atoms += "".join(f'<circle cx="{p(*f)[0]:.1f}" cy="{p(*f)[1]:.1f}" r="5" fill="{HOT}"/>' for f in faces)
    atoms += f'<circle class="pulse" cx="{cx}" cy="{cy}" r="8" fill="{AMBER}"/>'
    rows = [
        ("TARGET", "Cs0.05FA0.79MA0.16Pb(I0.83Br0.17)3"),
        ("AT", "1.2 M in 1 mL"),
        ("WITH", "5% B-site excess, 30 mol% MACl"),
        ("READ", "what to weigh, what to pipette"),
    ]
    text = ""
    for i, (k, v) in enumerate(rows):
        y = 96 + i * 34
        text += label(232, y, k, "kick", "start") + label(232, y + 17, v, "val", "start")
    legend = label(24 + 10, 224, "A", "ax", "start", f'style="fill:{TEAL}"') + label(24 + 24, 224, "B", "ax", "start", f'style="fill:{AMBER}"') + label(24 + 38, 224, "X", "ax", "start", f'style="fill:{HOT}"')
    return edges + octa + atoms + text + legend


def opv_db():
    tiers = [("Full archive", 38849, 1.0), ("Strict performance benchmark", 31360, 0.72), ("Strict molecular benchmark", 21720, 0.45)]
    out = ""
    x0, full = 40, 420
    for i, (name, n, op) in enumerate(tiers):
        y = 92 + i * 46
        width = full * n / tiers[0][1]
        out += label(x0, y, name, "ax", "start", f'style="font-size:13px;fill:{TEXT}"')
        out += f'<rect x="{x0}" y="{y + 7}" width="{width:.1f}" height="18" fill="{AMBER}" fill-opacity="{op}"/>'
        out += label(x0 + width + 10, y + 21, f"{n:,}", "lab", "start", 'style="font-size:15px"')
    return out


def swinglab():
    ground = 204
    bones = [((120, 94), (116, 108)), ((116, 108), (102, 150)), ((102, 150), (90, 176)), ((90, 176), (82, ground)), ((102, 150), (116, 176)), ((116, 176), (120, ground)), ((116, 108), (134, 134)), ((134, 134), (148, 158))]
    joints = sorted({p for bone in bones for p in bone})
    skeleton = "".join(f'<path d="M{a[0]} {a[1]} L{b[0]} {b[1]}" stroke="{TEAL}" stroke-width="2"/>' for a, b in bones)
    skeleton += "".join(f'<circle cx="{x}" cy="{y}" r="3.4" fill="{HOT}"/>' for x, y in joints)
    skeleton += f'<circle cx="120" cy="86" r="10" fill="none" stroke="{TEAL}" stroke-width="2"/>'
    club = f'<path d="M148 158 L198 200" stroke="{DIM}" stroke-width="2"/><path d="M60 92 A98 74 0 0 0 198 200 A120 96 0 0 0 268 118" class="dimline" stroke-dasharray="3 5"/>'

    # Ball flight with linear drag, sampled at equal time steps like a high-speed camera.
    k, vx, vy, g, dt = 0.32, 498.0, 176.0, 110.0, 0.02
    x, y, t = 206.0, 0.0, 0.0
    flight, tracer = [], ""
    i = 0
    while y >= 0:
        flight.append((x, ground - 4 - y))
        if i % 11 == 0:
            tracer += f'<circle cx="{x:.1f}" cy="{ground - 4 - y:.1f}" r="2.4" fill="{HOT}"/>'
        x += vx * dt
        y += vy * dt
        vx -= k * vx * dt
        vy -= (g + k * vy) * dt
        t += dt
        i += 1
    return (
        f'<path d="M24 {ground} H1200" class="dimline"/>'
        + skeleton
        + club
        + f'<circle cx="206" cy="{ground - 4}" r="4" fill="{HOT}"/>'
        + glow_trace(flight)
        + tracer
        + label(flight[len(flight) // 2][0], min(p[1] for p in flight) + 34, "240 fps launch monitor (experimental)", "ax", extra='style="font-size:13px"')
    )


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    card(out / "card-physiscore.svg", kick="THIN-FILM PHOTOVOLTAICS", title="Physiscore", right="PYTHON",
         desc=["Nine techniques, one set of conventions. Every number", "comes from the raw curve, not an instrument summary."],
         tags="J-V · EQE · Abs · PL · Raman · FTIR · XRD · SEM · XPS", body=physiscore())
    card(out / "card-xrd.svg", kick="X-RAY DIFFRACTION", title="XRD Analyzer", right="WIN · MAC · LINUX",
         desc=["Peak fits with uncertainties, Scherrer, Williamson-Hall.", "Missing inputs return NOT_CALCULABLE, never a guess."],
         tags="PYSIDE6 · CLI · PDF REPORTS · 294 TESTS", body=xrd())
    card(out / "card-nmr.svg", kick="NMR SPECTROSCOPY", title="NMR Analyzer", right="WIN · MAC · LINUX",
         desc=["1D and 2D spectra from Bruker, ACD/Labs and JCAMP-DX.", "Lineshape fits, integrals, SMILES structure check."],
         tags="TKINTER · NO THIRD-PARTY PACKAGES · 98 TESTS", body=nmr())
    card(out / "card-suya.svg", kick="SOUTHERN OCEAN", title="SUYA", right="WIN · MAC · LINUX",
         desc=["Continuously collects sea temperature, salinity and air", "temperature around Antarctica, provenance attached."],
         tags="PYSIDE6 · MATPLOTLIB · ENGLISH / 한국어 · 73 TESTS", body=suya())
    card(out / "card-calculator.svg", kick="SOLUTION PROCESSING", title="Solution Preparation Calculator", title_size=23, right="PYTHON STDLIB",
         desc=["Turns ABX3 compositions and donor:acceptor blends into", "the masses you weigh and the volumes you pipette."],
         tags="TKINTER · NOTHING TO INSTALL · CO-AUTHORED", body=calculator())
    card(out / "card-opvdb.svg", kick="LITERATURE-MINED DATASET", title="OPV-DB", right="CSV",
         desc=["Single-junction organic PV device records. Derived from", "Qiu's OPV-DB (CC BY 4.0), merged and filtered."],
         tags="MOLECULAR ⊂ PERFORMANCE ⊂ FULL · SMILES", body=opv_db())
    card(out / "card-swinglab.svg", kick="OFF THE BENCH", title="SwingLab", right="iOS 17+",
         desc=["Native iPhone golf lab: swing video with Vision pose, an experimental launch monitor,", "a club catalog since 2000 and course strategy. Honest provenance, 12 languages."],
         tags="SWIFT 6 · SWIFTUI · VISION · AVFOUNDATION · MAPKIT · 85 CORE + 40 APP TESTS",
         body=swinglab(), w=1224, h=320, plot=(24, 70, 1200, 212))


if __name__ == "__main__":
    main(sys.argv[1])
