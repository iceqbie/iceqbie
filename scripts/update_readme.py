"""Fill the "Latest posts" and "Papers" sections of README.md from the site's data.

    python3 scripts/update_readme.py                                  # fetch from iceqbie.github.io
    python3 scripts/update_readme.py --from-dir ~/iceqbie.github.io   # read a local site checkout

Run daily by .github/workflows/update-readme.yml. Only the text between the
<!-- posts:start/end --> and <!-- papers:start/end --> markers is replaced.
The site's lists are newest first, so the first entries are shown. If the
data can't be read, README.md is left alone.
"""

import argparse
import json
import pathlib
import sys
import urllib.error
import urllib.request

REPO = pathlib.Path(__file__).resolve().parent.parent
README = REPO / "README.md"
SITE = "https://iceqbie.github.io"
COUNT = 3


def load(name, from_dir):
    if from_dir:
        return json.loads((pathlib.Path(from_dir).expanduser() / "data" / name).read_text("utf-8"))
    with urllib.request.urlopen(f"{SITE}/data/{name}", timeout=30) as response:
        return json.load(response)


def posts(articles):
    lines = []
    for a in articles[:COUNT]:
        title = a["title"].get("en") or a["title"]["ja"]
        url = a["url"] if a["url"].startswith("http") else SITE + a["url"]
        note = " (in Japanese)" if a.get("lang") == "ja" else ""
        lines.append(f"- {a['date']} · [{title}]({url}){note}")
    return lines or ["- Nothing yet."]


def papers(publications):
    lines = []
    for p in publications[:COUNT]:
        links = " · ".join(f"[{l['label']}]({l['url']})" for l in p.get("links", []))
        lines.append(f"- **{p['title']}**, {p['journal']} ({p['year']})" + (f" · {links}" if links else ""))
    lines.append(f"- [All papers and talks]({SITE}/research/)")
    return lines


def replace(text, name, lines):
    start, end = f"<!-- {name}:start -->", f"<!-- {name}:end -->"
    head, rest = text.split(start, 1)
    _, tail = rest.split(end, 1)
    return head + start + "\n" + "\n".join(lines) + "\n" + end + tail


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-dir", help="read data/*.json from a local site checkout")
    args = parser.parse_args()
    try:
        articles = load("articles.json", args.from_dir)
        publications = load("publications.json", args.from_dir)
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as error:
        print(f"Could not read the site data, README left alone: {error}", file=sys.stderr)
        return
    text = README.read_text("utf-8")
    new = replace(replace(text, "posts", posts(articles)), "papers", papers(publications))
    if new != text:
        README.write_text(new, "utf-8")
        print("README.md updated")
    else:
        print("README.md unchanged")


if __name__ == "__main__":
    main()
