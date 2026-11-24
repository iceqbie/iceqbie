"""Draw the last year's contributions as stacked ice cubes, with a radar and a language pie.

    GITHUB_TOKEN=… python3 scripts/ice_contrib.py          # fetch from the GitHub GraphQL API
    python3 scripts/ice_contrib.py --from-file cal.json      # use a saved API response
    python3 scripts/ice_contrib.py --from-file cal.json --out /tmp/preview

Writes assets/ice-contrib-light.svg and assets/ice-contrib-dark.svg (shown in
README.md through <picture>). Run daily by .github/workflows/update-readme.yml
with the workflow's own GITHUB_TOKEN; no personal access token is needed.

- Calendar: each day stands on one cell (weeks left to right, Sunday at the
  back). A day with contributions gets 1–4 cubes, the same four levels GitHub's
  own calendar uses; the colour runs from Pale Ice to Deep Ice with the count.
- Radar (top right): commits, issues, pull requests, reviews and new
  repositories, on a log scale (1, 10, 100, 1K, 10K).
- Pie (bottom left): commits by the repository's main language, public
  repositories only, top five plus "other".

The output has no timestamps, so it only changes when the data does. If the
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
QUERY = """query($login: String!) { user(login: $login) { contributionsCollection {
  contributionCalendar { totalContributions weeks { contributionDays { date weekday contributionCount contributionLevel } } }
  totalCommitContributions totalIssueContributions totalPullRequestContributions
  totalPullRequestReviewContributions totalRepositoryContributions
  commitContributionsByRepository(maxRepositories: 100) {
    repository { isPrivate primaryLanguage { name } } contributions { totalCount } } } } }"""

# Site figure palette (iceqbie.github.io README → Colours): Pale Ice → Ice Blue → Mid Ice → Deep Ice
STOPS = ["#CBE5EF", "#A9D9E6", "#4D96B1", "#2F6F8A"]
PIE = ["#2F6F8A", "#4D96B1", "#A9D9E6", "#CBE5EF", "#7FB8CC"]   # by rank; "other" uses the theme's grey
LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
THEMES = {
    "light": {"tile": "#F5F6F7", "tile_edge": "#DCE2E6", "edge": "#2F6F8A", "edge_opacity": "0.8",
              "text": "#252A2E", "soft": "#5C6268", "grid": "#C4CBD1", "radar": "#2F6F8A",
              "radar_fill": "0.55", "gap": "#FFFFFF", "other": "#B8BEC4"},
    "dark": {"tile": "#1B2026", "tile_edge": "#2A3038", "edge": "#D7EEF6", "edge_opacity": "0.6",
             "text": "#E6EDF3", "soft": "#9DA7B1", "grid": "#3A424B", "radar": "#A9D9E6",
             "radar_fill": "0.35", "gap": "#0D1117", "other": "#5C6268"},
}
FONT = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
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


def collection(data):
    if data.get("errors"):
        raise ValueError(data["errors"])
    return data["data"]["user"]["contributionsCollection"]


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


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


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


def calendar_svg(cal, theme, ox, oy):
    days = [(col, d) for col, w in enumerate(cal["weeks"]) for d in w["contributionDays"]]
    days.sort(key=lambda x: (x[0] + x[1]["weekday"], x[0]))   # back to front
    most = max((d["contributionCount"] for _, d in days), default=0) or 1
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
    return "".join(body)


def radar_axes(c):
    return [("Commit", c["totalCommitContributions"]), ("Issue", c["totalIssueContributions"]),
            ("PullReq", c["totalPullRequestContributions"]), ("Review", c["totalPullRequestReviewContributions"]),
            ("Repo", c["totalRepositoryContributions"])]


def radar_svg(c, theme, cx, cy, r):
    axes = radar_axes(c)
    rings = ["1", "10", "100", "1K", "10K"]
    level = lambda v: 0.8 if v < 1 else min(math.log10(v), 5) + 1   # 1 → ring 1 … 10K → ring 5
    at = lambda lv, i: (cx + r * lv / len(rings) * math.sin(2 * math.pi * i / len(axes)),
                        cy - r * lv / len(rings) * math.cos(2 * math.pi * i / len(axes)))
    s = [f'<g font-family="{FONT}">']
    for k in range(1, len(rings) + 1):
        s.append(f'<polygon points="{pts([at(k, i) for i in range(len(axes))])}" fill="none" '
                 f'stroke="{theme["grid"]}" stroke-width="0.8" stroke-dasharray="3 3"/>')
    for i in range(len(axes)):
        x, y = at(len(rings), i)
        s.append(f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{x:.1f}" y2="{y:.1f}" stroke="{theme["grid"]}" stroke-width="0.8"/>')
    for k, label in enumerate(rings, 1):
        x, y = at(k, 0)
        s.append(f'<text x="{x + 2:.1f}" y="{y + 3:.1f}" font-size="8" fill="{theme["soft"]}">{label}</text>')
    shape = [at(level(v), i) for i, (_, v) in enumerate(axes)]
    s.append(f'<polygon points="{pts(shape)}" fill="{STOPS[1]}" fill-opacity="{theme["radar_fill"]}" '
             f'stroke="{theme["radar"]}" stroke-width="1.5" stroke-linejoin="round"/>')
    for i, (name, value) in enumerate(axes):
        x, y = at(len(rings) + 1.3, i)
        dx = math.sin(2 * math.pi * i / len(axes))
        anchor = "middle" if abs(dx) < 0.3 else ("start" if dx > 0 else "end")
        s.append(f'<text x="{x:.1f}" y="{y + 4:.1f}" text-anchor="{anchor}" font-size="11" fill="{theme["soft"]}">'
                 f'{name} <tspan fill="{theme["text"]}" font-weight="600">{value}</tspan></text>')
    s.append("</g>")
    return "".join(s)


def languages(c):
    totals = {}
    for item in c["commitContributionsByRepository"]:
        repo = item["repository"]
        if repo.get("isPrivate"):          # never show anything from private repositories
            continue
        name = (repo.get("primaryLanguage") or {}).get("name") or "other"
        totals[name] = totals.get(name, 0) + item["contributions"]["totalCount"]
    other = totals.pop("other", 0)
    ranked = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
    other += sum(n for _, n in ranked[5:])
    ranked = ranked[:5] + ([("other", other)] if other else [])
    return [(name, n) for name, n in ranked if n > 0]


def pie_svg(langs, theme, cx, cy, r):
    total = sum(n for _, n in langs)
    if not total:
        return ""
    s = [f'<g font-family="{FONT}">']
    angle = -math.pi / 2
    for i, (name, n) in enumerate(langs):
        colour = theme["other"] if name == "other" else PIE[i % len(PIE)]
        sweep = 2 * math.pi * n / total
        if len(langs) == 1:
            s.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{colour}"/>')
        else:
            x1, y1 = cx + r * math.cos(angle), cy + r * math.sin(angle)
            x2, y2 = cx + r * math.cos(angle + sweep), cy + r * math.sin(angle + sweep)
            large = 1 if sweep > math.pi else 0
            s.append(f'<path d="M{cx:.1f},{cy:.1f} L{x1:.1f},{y1:.1f} A{r},{r} 0 {large} 1 {x2:.1f},{y2:.1f} Z" '
                     f'fill="{colour}" stroke="{theme["gap"]}" stroke-width="1.5" stroke-linejoin="round"/>')
        angle += sweep
        y = cy - (len(langs) - 1) * 8 + i * 16
        s.append(f'<rect x="{cx + r + 14}" y="{y - 5}" width="10" height="10" rx="2" fill="{colour}" '
                 f'stroke="{theme["soft"]}" stroke-width="0.6"/>'
                 f'<text x="{cx + r + 30}" y="{y + 4}" font-size="11" fill="{theme["text"]}">{esc(name)} '
                 f'<tspan fill="{theme["soft"]}">{round(100 * n / total)}%</tspan></text>')
    s.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{theme["soft"]}" stroke-width="0.6"/>')
    s.append("</g>")
    return "".join(s)


def render(c, theme):
    cal = c["contributionCalendar"]
    weeks = len(cal["weeks"])
    ox, oy = -V[0] * 6 + 6, 4 * (CUBE + GAP) + 8
    width = ox + weeks * U[0] + 6
    height = oy + weeks * U[1] + 7 * V[1] + 6
    langs = languages(c)
    summary = ", ".join(f"{name} {value}" for name, value in radar_axes(c))
    lang_text = ", ".join(f"{name} {n}" for name, n in langs) or "none"
    label = (f"(ice)^3: {cal['totalContributions']} contributions in the last year, drawn as stacked ice cubes. "
             f"Radar: {summary}. Commits by language (public repositories): {lang_text}.")
    defs = ('<linearGradient id="gt" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFFFFF" stop-opacity="0.8"/>'
            '<stop offset="0.7" stop-color="#FFFFFF" stop-opacity="0.05"/></linearGradient>'
            '<linearGradient id="gf" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFFFFF" stop-opacity="0.5"/>'
            '<stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/></linearGradient>'
            '<linearGradient id="gs" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFFFFF" stop-opacity="0.25"/>'
            '<stop offset="1" stop-color="#000000" stop-opacity="0.1"/></linearGradient>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" width="{width:.0f}" '
            f'height="{height:.0f}" role="img" aria-labelledby="title"><title id="title">{esc(label)}</title>'
            f'<defs>{defs}</defs>'
            + radar_svg(c, theme, width - 112, 70, 46)           # top right, drawn first so cubes stay in front
            + calendar_svg(cal, theme, ox, oy)
            + pie_svg(langs, theme, 50, height - 52, 34)          # bottom left
            + '</svg>\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-file", help="read a saved GraphQL response instead of calling the API")
    parser.add_argument("--out", help="write the images here instead of assets/ (for previews)")
    args = parser.parse_args()
    try:
        data = json.loads(pathlib.Path(args.from_file).read_text("utf-8")) if args.from_file else fetch()
        c = collection(data)
        c["contributionCalendar"]["weeks"]
    except (OSError, urllib.error.URLError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        print(f"Could not read the contribution data, images left alone: {error}", file=sys.stderr)
        return
    out = pathlib.Path(args.out).expanduser() if args.out else OUT
    out.mkdir(exist_ok=True)
    for name, theme in THEMES.items():
        path = out / f"ice-contrib-{name}.svg"
        svg = render(c, theme)
        if not path.exists() or path.read_text("utf-8") != svg:
            path.write_text(svg, "utf-8")
            print(f"{path.name} updated")
        else:
            print(f"{path.name} unchanged")


if __name__ == "__main__":
    main()
