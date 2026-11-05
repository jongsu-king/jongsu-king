"""Shared look for the generated figures: two themes, one accent, journal-style axes."""
from xml.sax.saxutils import escape

FONT = "-apple-system,BlinkMacSystemFont,'Helvetica Neue',Helvetica,Arial,sans-serif"

# Backgrounds match GitHub's canvas, so figures sit on the page without a visible box,
# yet stay readable if a viewer's site theme and system theme disagree.
THEMES = {
    "dark": {
        "bg": "#0d1117", "ink": "#e6edf3", "sub": "#9198a1", "axis": "#6e7681", "accent": "#ffb000",
        "ramp": ["#0d1117", "#3d2b08", "#a87400", "#ffb000", "#ffe9b0"],
    },
    "light": {
        "bg": "#ffffff", "ink": "#1f2328", "sub": "#59636e", "axis": "#818b98", "accent": "#cf2f0e",
        "ramp": ["#ffffff", "#fcdccb", "#f08a6c", "#cf2f0e", "#6e1405"],
    },
}


def hex_rgb(value):
    return tuple(int(value[i : i + 2], 16) for i in (1, 3, 5))


def ramp_color(theme, v):
    """Map v in [0, 1] onto the theme's sequential ramp."""
    stops = theme["ramp"]
    v = max(0.0, min(1.0, v)) * (len(stops) - 1)
    i = min(int(v), len(stops) - 2)
    a, b = hex_rgb(stops[i]), hex_rgb(stops[i + 1])
    k = v - i
    return "#%02x%02x%02x" % tuple(round(a[c] + (b[c] - a[c]) * k) for c in range(3))


def text(x, y, s, fill, size=13, anchor="start", weight=None, extra=""):
    bold = f' font-weight="{weight}"' if weight else ""
    return f'<text x="{x:.1f}" y="{y:.1f}" fill="{fill}" font-size="{size}" text-anchor="{anchor}"{bold} {extra}>{escape(s)}</text>'


def path(points, stroke, width=1.2, fill="none", extra=""):
    d = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in points)
    return f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{width}" stroke-linejoin="round" {extra}/>'


def document(w, h, theme, body, label):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{escape(label)}">'
        f'<style>text{{font-family:{FONT}}}</style><rect width="{w}" height="{h}" fill="{theme["bg"]}"/>{body}</svg>\n'
    )


class Axes:
    """A despined plot: left and bottom spines, outward ticks, nothing else."""

    def __init__(self, theme, box, xlim, ylim):
        self.t, self.box, self.xlim, self.ylim = theme, box, xlim, ylim

    def x(self, v):
        x0, _, x1, _ = self.box
        return x0 + (v - self.xlim[0]) / (self.xlim[1] - self.xlim[0]) * (x1 - x0)

    def y(self, v):
        _, y0, _, y1 = self.box
        return y1 - (v - self.ylim[0]) / (self.ylim[1] - self.ylim[0]) * (y1 - y0)

    def draw(self, xticks, yticks=(), xlabel="", ylabel="", size=12.5):
        t = self.t
        x0, y0, x1, y1 = self.box
        out = f'<path d="M{x0} {y1} H{x1}" stroke="{t["axis"]}"/>'
        for v in xticks:
            px = self.x(v)
            out += f'<path d="M{px:.1f} {y1} v4" stroke="{t["axis"]}"/>' + text(px, y1 + 18, str(v), t["sub"], size, "middle")
        if yticks:
            out += f'<path d="M{x0} {y0} V{y1}" stroke="{t["axis"]}"/>'
            for v in yticks:
                py = self.y(v)
                out += f'<path d="M{x0} {py:.1f} h-4" stroke="{t["axis"]}"/>' + text(x0 - 7, py + 4, str(v), t["sub"], size, "end")
        if xlabel:
            out += text((x0 + x1) / 2, y1 + 37, xlabel, t["sub"], size, "middle")
        if ylabel:
            cy = (y0 + y1) / 2
            out += text(13, cy, ylabel, t["sub"], size, "middle", extra=f'transform="rotate(-90 13 {cy})"')
        return out
