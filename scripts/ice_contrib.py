"""Draw the last year's contribution calendar as stacked ice cubes.

    GITHUB_TOKEN=… python3 scripts/ice_contrib.py          # fetch from the GitHub GraphQL API
    python3 scripts/ice_contrib.py --from-file cal.json      # use a saved API response

Writes assets/ice-contrib-light.svg and assets/ice-contrib-dark.svg (shown in
README.md through <picture>). Run daily by .github/workflows/update-readme.yml
with the workflow's own GITHUB_TOKEN; no personal access token is needed.

Each day stands on one cell (weeks left to right, Sunday at the back). A day
with contributions gets 1–4 cubes, the same four levels GitHub's own calendar
uses; the colour runs from Pale Ice to Deep Ice with the day's count. The
output has no timestamps, so it only changes when the calendar does. If the
data can't be read, the images are left alone.
"""

import argparse
import json
import math
import os
import pathlib
import sys
import urllib.error
import urllib.request

REPO = pathlib.Path(__file__).resolve().parent.parent
OUT = REPO / "assets"
USER = "iceqbie"
QUERY = """query($login: String!) { user(login: $login) { contributionsCollection { contributionCalendar {
  totalContributions weeks { contributionDays { date weekday contributionCount contributionLevel } } } } } }"""

# Site figure palette (iceqbie.github.io README → Colours): Pale Ice → Ice Blue → Mid Ice → Deep Ice
STOPS = ["#CBE5EF", "#A9D9E6", "#4D96B1", "#2F6F8A"]
LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
THEMES = {
    "light": {"tile": "#F5F6F7", "tile_edge": "#DCE2E6", "edge": "#2F6F8A", "edge_opacity": "0.8"},
    "dark": {"tile": "#1B2026", "tile_edge": "#2A3038", "edge": "#D7EEF6", "edge_opacity": "0.6"},
}
U = (11.0, 3.6)    # one week to the right
V = (-6.0, 5.2)    # one weekday towards the viewer
CUBE = 9.0         # height of one cube
GAP = 0.6          # gap between stacked cubes
WHITE, INK = (255, 255, 255), (0x25, 0x2A, 0x2E)


def fetch():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise OSError("GITHUB_TOKEN is not set")
    body = json.dumps({"query": QUERY, "variables": {"login": USER}}).encode()
    request = urllib.request.Request("https://api.github.com/graphql", data=body, headers={
        "Authorization": f"bearer {token}", "Content-Type": "application/json", "User-Agent": "ice-contrib"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def calendar(data):
    if data.get("errors"):
        raise ValueError(data["errors"])
    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def hexa(c):
    return "#" + "".join(f"{max(0, min(255, round(v))):02X}" for v in c)


def mix(c, other, f):
    return tuple(c[k] + (other[k] - c[k]) * f for k in range(3))


def ramp(t):
    t = max(0.0, min(1.0, t)) * (len(STOPS) - 1)
    i = min(int(t), len(STOPS) - 2)
    return mix(rgb(STOPS[i]), rgb(STOPS[i + 1]), t - i)


def add(p, q):
    return (p[0] + q[0], p[1] + q[1])


def pts(ps):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in ps)


def cube(p0, z0, colour, theme):
    """One translucent ice cube on ground cell p0, from height z0 to z0 + CUBE."""
    ground = [p0, add(p0, U), add(add(p0, U), V), add(p0, V)]
    b = [(x, y - z0) for x, y in ground]
    t = [(x, y - z0 - CUBE) for x, y in ground]
    faces = (([b[1], b[2], t[2], t[1]], mix(colour, INK, 0.2), "gs"),   # right face
             ([b[3], b[2], t[2], t[3]], colour, "gf"),                  # front face
             (t, mix(colour, WHITE, 0.5), "gt"))                         # top face
    s = []
    for face, fill, gloss in faces:
        s.append(f'<polygon points="{pts(face)}" fill="{hexa(fill)}" fill-opacity="0.86"/>'
                 f'<polygon points="{pts(face)}" fill="url(#{gloss})"/>')
    s.append(f'<polygon points="{pts([t[0], t[1], t[2], b[2], b[3], t[3]])}" fill="none" stroke="{theme["edge"]}" '
             f'stroke-opacity="{theme["edge_opacity"]}" stroke-width="0.7" stroke-linejoin="round"/>')
    s.append(f'<polyline points="{pts([t[3], t[2], t[1]])}" fill="none" stroke="#FFFFFF" stroke-opacity="0.95" '
             f'stroke-width="1" stroke-linecap="round"/>')
    x = b[3][0] + (b[2][0] - b[3][0]) * 0.22
    y = b[3][1] + (b[2][1] - b[3][1]) * 0.22
    s.append(f'<line x1="{x:.1f}" y1="{y - CUBE + 2.5:.1f}" x2="{x:.1f}" y2="{y - CUBE * 0.45:.1f}" '
             f'stroke="#FFFFFF" stroke-opacity="0.7" stroke-width="1.1" stroke-linecap="round"/>')
    return "".join(s)


def render(cal, theme):
    days = [(col, d) for col, w in enumerate(cal["weeks"]) for d in w["contributionDays"]]
    days.sort(key=lambda x: (x[0] + x[1]["weekday"], x[0]))   # back to front
    most = max((d["contributionCount"] for _, d in days), default=0) or 1
    ox, oy = -V[0] * 6 + 6, 4 * (CUBE + GAP) + 8
    body = []
    for col, d in days:
        p0 = (ox + col * U[0] + d["weekday"] * V[0], oy + col * U[1] + d["weekday"] * V[1])
        n = d["contributionCount"]
        if n == 0:
            body.append(f'<polygon points="{pts([p0, add(p0, U), add(add(p0, U), V), add(p0, V)])}" '
                        f'fill="{theme["tile"]}" stroke="{theme["tile_edge"]}" stroke-width="0.6"/>')
            continue
        t = math.sqrt(n / most)
        level = LEVELS.get(d.get("contributionLevel"), 0) or max(1, math.ceil(4 * t))
        colour = ramp(t)
        body.append(f'<g><title>{d["date"]}: {n} contribution{"" if n == 1 else "s"}</title>'
                    + "".join(cube(p0, k * (CUBE + GAP), colour, theme) for k in range(level)) + "</g>")
    weeks = len(cal["weeks"])
    width = ox + weeks * U[0] + 6
    height = oy + weeks * U[1] + 7 * V[1] + 6
    label = f"(ice)^3: {cal['totalContributions']} contributions in the last year, drawn as stacked ice cubes"
    defs = ('<linearGradient id="gt" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFFFFF" stop-opacity="0.8"/>'
            '<stop offset="0.7" stop-color="#FFFFFF" stop-opacity="0.05"/></linearGradient>'
            '<linearGradient id="gf" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFFFFF" stop-opacity="0.5"/>'
            '<stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/></linearGradient>'
            '<linearGradient id="gs" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFFFFF" stop-opacity="0.25"/>'
            '<stop offset="1" stop-color="#000000" stop-opacity="0.1"/></linearGradient>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" width="{width:.0f}" '
            f'height="{height:.0f}" role="img" aria-labelledby="title"><title id="title">{label}</title>'
            f'<defs>{defs}</defs>{"".join(body)}</svg>\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-file", help="read a saved GraphQL response instead of calling the API")
    args = parser.parse_args()
    try:
        data = json.loads(pathlib.Path(args.from_file).read_text("utf-8")) if args.from_file else fetch()
        cal = calendar(data)
    except (OSError, urllib.error.URLError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        print(f"Could not read the contribution calendar, images left alone: {error}", file=sys.stderr)
        return
    OUT.mkdir(exist_ok=True)
    for name, theme in THEMES.items():
        path = OUT / f"ice-contrib-{name}.svg"
        svg = render(cal, theme)
        if not path.exists() or path.read_text("utf-8") != svg:
            path.write_text(svg, "utf-8")
            print(f"{path.relative_to(REPO)} updated")
        else:
            print(f"{path.relative_to(REPO)} unchanged")


if __name__ == "__main__":
    main()
