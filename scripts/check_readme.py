#!/usr/bin/env python3
"""Request every image and link in the rendered profile README and report what fails.

Each URL gets three tries, so a slow answer isn't reported as a dead one. Images hosted
outside GitHub are listed separately, because each one can fail for every visitor when that
host is slow. Sites that turn away scripts (403, 429) are reported as blocked, not dead.

Exits with 1 if anything is dead or an image is blocked.

Usage: GH_TOKEN=... check_readme.py OWNER/REPO   (standard library only)
"""
import concurrent.futures
import os
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlparse

TRIES = 3
TIMEOUT = 20
SLOW_SECONDS = 4
GITHUB_HOSTS = ("github.com", "raw.githubusercontent.com", "camo.githubusercontent.com")


class Collector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "img":
            self.urls.setdefault(attrs.get("data-canonical-src") or attrs.get("src"), "image")
        elif tag == "source":
            self.urls.setdefault(attrs.get("srcset"), "image")
        elif tag == "a" and (attrs.get("href") or "").startswith("http"):
            self.urls.setdefault(attrs["href"], "link")


def rendered_readme(repo):
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/readme",
        headers={"Accept": "application/vnd.github.html", "Authorization": f"bearer {os.environ['GH_TOKEN']}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def probe(url):
    """Return (status, seconds of the fastest good try or the last try), retrying failures."""
    status, seconds = "no answer", 0.0
    for attempt in range(TRIES):
        if attempt:
            time.sleep(2 * attempt)
        started = time.monotonic()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (profile link check)"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                resp.read(1024)
                status = resp.status
        except urllib.error.HTTPError as err:
            status = err.code
        except OSError as err:
            status = type(getattr(err, "reason", err)).__name__
        seconds = time.monotonic() - started
        if status == 200:
            break
    return status, seconds


def main(repo):
    collector = Collector()
    collector.feed(rendered_readme(repo))
    urls = {u: kind for u, kind in collector.urls.items() if u}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        results = dict(zip(urls, pool.map(probe, urls)))

    dead, blocked, slow, outside = [], [], [], []
    for url, (status, seconds) in results.items():
        line = f"{urls[url]:5} {status!s:>10} {seconds:5.1f}s  {url}"
        if status in (403, 429):
            blocked.append(line)
        elif status != 200:
            dead.append(line)
        elif seconds > SLOW_SECONDS:
            slow.append(line)
        if urls[url] == "image" and urlparse(url).hostname not in GITHUB_HOSTS:
            outside.append(line)

    print(f"Checked {len(urls)} URLs: {sum(k == 'image' for k in urls.values())} images, {sum(k == 'link' for k in urls.values())} links.")
    for title, lines in (("Dead", dead), ("Blocked scripts", blocked), ("Slow", slow), ("Images hosted outside GitHub", outside)):
        print(f"\n{title}: {len(lines)}")
        print("\n".join(lines) if lines else "  none")
    if dead or any(line.startswith("image") for line in blocked):
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1])
