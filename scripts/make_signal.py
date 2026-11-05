#!/usr/bin/env python3
"""Generate the activity figure from GitHub's GraphQL API, in both themes.

The last 26 weeks of the contribution calendar as a dot-matrix panel, the same two
instruments as the hero: an LED display in dark mode, halftone print on chart paper in
light mode. Under it, on the same time axis, a stick spectrum with one line per active day.
GitHub's own calendar sits further down the profile and shows the full year.

Every dot and stick is a day's real count. Private repositories are dropped from the
commit list even when the token can see them, and the profile repository is named after
the user and isn't one of the projects.

Usage: GH_TOKEN=... make_signal.py USER OUTPUT_DIR   (standard library only)
"""
import datetime as dt
import json
import math
import os
import sys
import urllib.request
from pathlib import Path

from figstyle import THEMES, document, ramp_color, text

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
      commitContributionsByRepository(maxRepositories: 10) {
        repository { name isPrivate }
        contributions { totalCount }
      }
    }
  }
}
"""
WEEKS_SHOWN = 26
W, H = 820, 372
X0, X1 = 40, 812
PITCH = (X1 - X0) / WEEKS_SHOWN
PANEL_TOP = 2
PANEL_BOTTOM = PANEL_TOP + 7 * PITCH
STICKS = (PANEL_BOTTOM + 18, PANEL_BOTTOM + 86)  # y of the tallest possible stick, y of the axis
CYCLE = 12  # seconds between beam passes
SWEEP = 2.6  # seconds a pass takes

PANELS = {
    "dark": {"fill": "#0b0b09", "edge": "#2e2a1a", "grid": None, "off": "#272112"},
    "light": {"fill": "#f8f3e7", "edge": "#e5bba4", "grid": "#f0ddcd", "off": None},
}


def fetch(user):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": user}}).encode(),
        headers={"Authorization": f"bearer {os.environ['GH_TOKEN']}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if payload.get("errors"):
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    return payload["data"]["user"]["contributionsCollection"]


def nice_ticks(value):
    for step in (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500):
        top = math.ceil(value / step) * step
        if top / step <= 3:
            return top, list(range(0, top + 1, step))
    return value, [0, value]


def sweep_style():
    share = SWEEP / CYCLE * 100
    distance = X1 - X0
    return (
        f".beam{{stroke-width:1.5;opacity:0;animation:beam {CYCLE}s linear infinite}}"
        f"@keyframes beam{{0%{{transform:translateX(0);opacity:.8}}{share:.1f}%{{transform:translateX({distance}px);opacity:.8}}"
        f"{share + 0.01:.2f}%,100%{{transform:translateX({distance}px);opacity:0}}}}"
        f".lit{{transform-box:fill-box;transform-origin:center;animation:flash {CYCLE}s linear infinite}}"
        "@keyframes flash{0%{transform:scale(1.3)}5%,100%{transform:scale(1)}}"
        "@media (prefers-reduced-motion:reduce){.beam,.lit{animation:none}}"
    )


def panel_background(panel):
    out = f'<rect x="{X0}" y="{PANEL_TOP}" width="{X1 - X0}" height="{7 * PITCH:.1f}" rx="{4 if panel["grid"] is None else 0}" fill="{panel["fill"]}"/>'
    if panel["grid"]:
        lines = "".join(f'M{X0 + c * PITCH:.1f} {PANEL_TOP} V{PANEL_BOTTOM:.1f}' for c in range(1, WEEKS_SHOWN))
        lines += "".join(f'M{X0} {PANEL_TOP + r * PITCH:.1f} H{X1}' for r in range(1, 7))
        out += f'<path d="{lines}" stroke="{panel["grid"]}" fill="none"/>'
    return out


def activity(mode, theme, data, user, today):
    calendar = data["contributionCalendar"]
    panel = PANELS[mode]
    weeks = calendar["weeks"][-WEEKS_SHOWN:]
    shown = [d["contributionCount"] for w in weeks for d in w["contributionDays"]]
    top_count = max(shown, default=0) or 1
    active_days = sum(d["contributionCount"] > 0 for w in calendar["weeks"] for d in w["contributionDays"])

    off, bloom, dots, active = "", "", "", []
    positions = {}
    for column, week in enumerate(weeks):
        for day in week["contributionDays"]:
            date = dt.date.fromisoformat(day["date"])
            row = date.isoweekday() % 7  # GitHub's calendar starts its weeks on Sunday
            cx = X0 + (column + 0.5) * PITCH
            cy = PANEL_TOP + (row + 0.5) * PITCH
            positions[date] = (cx, cy)
            count = day["contributionCount"]
            if not count:
                if panel["off"]:
                    off += f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="5.4"/>'
                continue
            active.append((date, count))
            k = math.sqrt(count / top_count)
            delay = (cx - X0) / (X1 - X0) * SWEEP
            if mode == "dark":
                # An LED says it with brightness: every lit dot is about the same size.
                r = 8.2 + 3 * k
                fill = ramp_color(theme, 0.52 + 0.33 * k)
                bloom += f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r + 3.5:.1f}" fill="{theme["accent"]}" opacity="{0.22 + 0.33 * k:.2f}"/>'
            else:
                # Halftone print says it with dot size.
                r = 4 + 8.6 * k
                fill = ramp_color(theme, 0.66 + 0.2 * k)
            dots += f'<circle class="lit" style="animation-delay:{delay:.2f}s" cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}"/>'

    body = '<defs><filter id="bloom" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="4.5"/></filter></defs>'
    body += panel_background(panel)
    for row, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        body += text(X0 - 8, PANEL_TOP + (row + 0.5) * PITCH + 4, name, theme["sub"], 11.5, "end")
    if off:
        body += f'<g fill="{panel["off"]}">{off}</g>'
    if bloom:
        body += f'<g filter="url(#bloom)">{bloom}</g>'
    body += dots

    if today in positions:
        cx, cy = positions[today]
        body += f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{PITCH / 2 - 1.2:.1f}" fill="none" stroke="{theme["ink"]}" stroke-width="1.2"/>'

    y0, y1 = STICKS
    top, yticks = nice_ticks(top_count * 1.25)
    fy = lambda v: y1 - v / top * (y1 - y0)
    stick_x = lambda date: positions[date][0] - PITCH / 2 + (date.isoweekday() % 7 + 0.5) / 7 * PITCH
    for date, count in active:
        body += f'<path d="M{stick_x(date):.1f} {y1:.1f} V{fy(count):.1f}" stroke="{theme["accent"]}" stroke-width="2.4"/>'
    placed = []
    for date, count in sorted(active, key=lambda item: -item[1]):
        x = stick_x(date)
        if len(placed) < 6 and all(abs(x - other) > 66 for other in placed):
            placed.append(x)
            anchor = "end" if x > X1 - 34 else "middle"
            body += text(x, fy(count) - 5, f"{date:%b} {date.day}: {count}", theme["ink"], 11.5, anchor)

    body += f'<path d="M{X0} {y1:.1f} H{X1}" stroke="{theme["axis"]}"/><path d="M{X0} {y0:.1f} V{y1:.1f}" stroke="{theme["axis"]}"/>'
    for v in yticks:
        body += f'<path d="M{X0} {fy(v):.1f} h-4" stroke="{theme["axis"]}"/>' + text(X0 - 7, fy(v) + 4, str(v), theme["sub"], 11.5, "end")
    for date in sorted(positions):
        if date.day == 1:
            x = stick_x(date)
            body += f'<path d="M{x:.1f} {y1:.1f} v4" stroke="{theme["axis"]}"/>' + text(x, y1 + 18, f"{date:%b}", theme["sub"], 12, "middle")

    repos = sorted(
        ((r["repository"]["name"], r["contributions"]["totalCount"]) for r in data["commitContributionsByRepository"]
         if not r["repository"]["isPrivate"] and r["repository"]["name"] != user),
        key=lambda r: -r[1],
    )
    summary = f"{calendar['totalContributions']} contributions on {active_days} days in the last 12 months."
    body += text(X0, H - 24, summary, theme["ink"], 13)
    if repos:
        body += text(X0, H - 6, "Commits: " + ", ".join(f"{name} {n}" for name, n in repos[:5]), theme["sub"], 12.5)
    body += f'<path class="beam" d="M{X0} {PANEL_TOP} V{y1:.1f}" stroke="{theme["accent"]}"/>'
    return document(W, H, theme, body, summary, sweep_style())


def main(user, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    data = fetch(user)
    today = dt.datetime.now(dt.timezone.utc).date()
    for mode, theme in THEMES.items():
        (out / f"activity-{mode}.svg").write_text(activity(mode, theme, data, user, today), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
