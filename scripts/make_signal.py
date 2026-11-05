#!/usr/bin/env python3
"""Generate the activity figure from GitHub's GraphQL API, in both themes.

A stick spectrum: one line per active day, its height that day's contributions. Nothing
is smoothed or padded, and private repositories are dropped even when the token can see
them. The profile repository is named after the user and isn't one of the projects.

Usage: GH_TOKEN=... make_signal.py USER OUTPUT_DIR   (standard library only)
"""
import datetime as dt
import json
import math
import os
import sys
import urllib.request
from pathlib import Path

from figstyle import THEMES, Axes, document, text

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
W, H = 820, 250
BOX = (40, 26, 812, 182)


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
        if top / step <= 4:
            return top, list(range(0, top + 1, step))
    return value, [0, value]


def activity(theme, data, user, today):
    calendar = data["contributionCalendar"]
    days = [d for week in calendar["weeks"] for d in week["contributionDays"]]
    active = [(dt.date.fromisoformat(d["date"]), d["contributionCount"]) for d in days if d["contributionCount"] > 0]
    first = active[0][0] if active else today
    start = max(today - dt.timedelta(days=365), min(first - dt.timedelta(days=10), today - dt.timedelta(days=90)))
    end = today + dt.timedelta(days=2)
    top, yticks = nice_ticks(max((c for _, c in active), default=1) * 1.12)

    ax = Axes(theme, BOX, (0, (end - start).days), (0, top))
    fx = lambda d: ax.x((d - start).days)
    body = ""
    for d, c in active:
        body += f'<path d="M{fx(d):.1f} {ax.y(0):.1f} V{ax.y(c):.1f}" stroke="{theme["accent"]}" stroke-width="2.4"/>'

    placed = []
    for d, c in sorted(active, key=lambda item: -item[1]):
        x = fx(d)
        if len(placed) < 7 and all(abs(x - other) > 58 for other in placed):
            placed.append(x)
            anchor = "end" if x > BOX[2] - 34 else "middle"
            body += text(x, ax.y(c) - 6, f"{d:%b} {d.day}: {c}", theme["ink"], 12, anchor)

    # Month ticks stand in for the numeric x axis that Axes would otherwise draw.
    body += ax.draw((), (), "")
    month = dt.date(start.year, start.month, 1)
    while month <= today:
        if month >= start:
            body += f'<path d="M{fx(month):.1f} {BOX[3]} v4" stroke="{theme["axis"]}"/>'
            body += text(fx(month), BOX[3] + 18, f"{month:%b}", theme["sub"], 12.5, "middle")
        month = dt.date(month.year + (month.month == 12), month.month % 12 + 1, 1)
    body += f'<path d="M{BOX[0]} {BOX[1]} V{BOX[3]}" stroke="{theme["axis"]}"/>'
    for v in yticks:
        body += f'<path d="M{BOX[0]} {ax.y(v):.1f} h-4" stroke="{theme["axis"]}"/>' + text(BOX[0] - 7, ax.y(v) + 4, str(v), theme["sub"], 12.5, "end")

    repos = sorted(
        ((r["repository"]["name"], r["contributions"]["totalCount"]) for r in data["commitContributionsByRepository"]
         if not r["repository"]["isPrivate"] and r["repository"]["name"] != user),
        key=lambda r: -r[1],
    )
    summary = f"{calendar['totalContributions']} contributions on {len(active)} days, last 12 months."
    body += text(BOX[0], H - 24, summary, theme["ink"], 13)
    if repos:
        body += text(BOX[0], H - 6, "Commits: " + ", ".join(f"{name} {n}" for name, n in repos[:5]), theme["sub"], 12.5)
    return document(W, H, theme, body, summary)


def main(user, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    data = fetch(user)
    today = dt.datetime.now(dt.timezone.utc).date()
    for mode, theme in THEMES.items():
        (out / f"activity-{mode}.svg").write_text(activity(theme, data, user, today), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
