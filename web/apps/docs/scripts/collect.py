"""Each package's documentation, as pages of this site.

    uv run python web/apps/docs/scripts/collect.py

Writes every page an index lists into src/content/docs/<section>/ (not
committed): the title from the page's heading, the order and description from
its index, each `::code{...}` expanded by `contraagent._internal.docs.expand` (the one
implementation `contraagent docs` uses too), each link pointed at the page it
names. A quote or a link that does not resolve stops it, and so does an HTML
tag in a page's prose (outside code), which the site would render. An image a page shows
(`![...](images/x.png)`) is copied beside the collected page, so its relative
link still holds; an image whose file is missing is left out, with a warning.
The JSON Schemas of the Python package's files (`contraagent/docs/schemas/`) go
into public/schemas/, served as they are.

`LIVE` is the site's own part of the element topics: the live elements each one
shows under its title (the page's `live` front matter, drawn by
`src/components/LiveFigures.astro`).
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

from contraagent._internal import docs

ROOT = Path(__file__).resolve().parents[4]
CONTENT = Path(__file__).resolve().parents[1] / "src" / "content" / "docs"
SCHEMAS = Path(__file__).resolve().parents[1] / "public" / "schemas"

#: Each package's index, the directory its quotes are relative to, the site section it becomes, and its name.
SECTIONS = [
    (docs.INDEX, docs.DIR, "python", "Python package"),
    (ROOT / "web/packages/api/README.md", ROOT / "web/packages/api", "node/api", "@contraagent/api"),
    (ROOT / "web/packages/ui/README.md", ROOT / "web/packages/ui", "node/ui", "@contraagent/ui"),
    (ROOT / "web/packages/elements/README.md", ROOT / "web/packages/elements", "node/elements", "@contraagent/elements"),
]
LINK = re.compile(r"\]\(([^)\s]+)\)")
IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".avif"}
FENCE = re.compile(r"^\s*```")
CODE_SPAN = re.compile(r"(`+)[\s\S]+?\1")
HTML_TAG = re.compile(r"<!--|</?[A-Za-z][\w-]*(\s[^<>]*)?/?>")
MANIFESTS = [ROOT / "web/packages/ui/custom-elements.json", ROOT / "web/packages/elements/custom-elements.json"]


def demo(tag: str, props: dict[str, str], **more: object) -> dict:
    """A `ca-*` view fed with the demo pipeline's run (src/fixtures/demo-run.json); `props` maps its properties to the fixture's keys."""
    return {"demo": tag, "props": props, "tags": [tag], **more}


def example(name: str, *tags: str, **more: object) -> dict:
    """`@contraagent/elements`' example `docs/examples/<name>.ts`, mounted; `tags` are the elements it shows."""
    return {"example": name, "tags": list(tags), **more}


def picture(path: str, alt: str, *tags: str) -> dict:
    """A screenshot in the repository (`docs/assets/readme/`), for a view that needs a monitor behind it."""
    return {"image": path, "alt": alt, "tags": list(tags)}


RUN = {"plan": "plan", "journal": "journal", "run": "run"}

#: A topic page (section/name) and the live elements under its title, in order.
LIVE: dict[str, list[dict]] = {
    "node/ui/index": [
        picture(
            "docs/assets/readme/overview.png",
            "The monitor's overview of the demo run: its state, problems with their causes, outputs and the pipeline graph",
            "ca-monitor",
        )
    ],
    "node/ui/embed": [
        picture(
            "docs/assets/readme/task-detail.png",
            "The monitor's task detail: an attempt's transcript, its tokens and cost, and its checked output",
            "ca-monitor",
        )
    ],
    "node/ui/live-data": [demo("ca-journal-table", {"rows": "journal", "plan": "plan"}, height="360px")],
    "node/ui/events": [demo("ca-pipeline-graph", RUN)],
    "node/ui/theming": [
        demo("ca-kpis", {"journal": "journal"}, caption="contraagent-dark"),
        demo("ca-kpis", {"journal": "journal"}, theme="github-light", caption="github-light"),
        demo(
            "ca-kpis",
            {"journal": "journal"},
            theme="contraagent-light",
            custom="solarized-light",
            caption="solarized-light, a theme of one's own (@contraagent/elements docs/examples/theme.css)",
        ),
    ],
    "node/elements/index": [
        example("ci-pipeline", "cae-segmented", "cae-stat-tiles", "cae-data-table", "cae-layered-graph", height="640px")
    ],
    "node/elements/primitives": [example("status"), example("segmented", "cae-segmented")],
    "node/elements/theming": [
        example("tiles", "cae-stat-tiles", caption="contraagent-dark"),
        example("tiles", theme="github-light", caption="github-light"),
        example(
            "tiles",
            theme="contraagent-light",
            custom="solarized-light",
            caption="solarized-light, a theme of one's own (docs/examples/theme.css)",
        ),
    ],
    "node/elements/data-table": [example("data-table", "cae-data-table")],
    "node/elements/graph": [example("graph", "cae-layered-graph", height="420px")],
    "node/elements/matrix": [example("matrix", "cae-mark-matrix")],
    "node/elements/tiles": [example("tiles", "cae-stat-tiles")],
    "node/elements/lanes": [example("lanes", "cae-lanes")],
    "node/elements/charts": [example("charts", "cae-column-chart", "cae-line-chart", "cae-heatmap", "cae-bar-chart")],
    "node/elements/check-table": [example("check-table", "cae-check-table")],
    "node/elements/transcript": [example("transcript", "cae-transcript")],
    "node/elements/page": [example("ci-pipeline", height="640px")],
}


def main() -> None:
    pages: dict[Path, dict] = {}
    for index, root, section, package in SECTIONS:
        pages[index.resolve()] = {
            "root": root,
            "url": f"/{section}/",
            "out": CONTENT / section / "index.md",
            "key": f"{section}/index",
            "order": 0,
            "label": "Overview",
            "head": f"{package} | contraagent",
        }
        for order, entry in enumerate(docs.entries(index), 1):
            pages[entry.path] = {
                "root": root,
                "url": f"/{section}/{entry.name}/",
                "out": CONTENT / section / f"{entry.name}.md",
                "key": f"{section}/{entry.name}",
                "order": order,
                "description": entry.summary,
                # Two packages have a "Theming": a web package's tab names the package.
                "head": None if section == "python" else f"{entry.title} | {package}",
            }
    check_live({page["key"] for page in pages.values()})
    for _, _, section, _ in SECTIONS:
        shutil.rmtree(CONTENT / section, ignore_errors=True)
    for source, page in pages.items():
        page["out"].parent.mkdir(parents=True, exist_ok=True)
        page["out"].write_text(render(source, page, pages))
    shutil.rmtree(SCHEMAS, ignore_errors=True)
    shutil.copytree(docs.DIR / "schemas", SCHEMAS)
    sys.stdout.write(f"collected {len(pages)} pages and {len(list(SCHEMAS.glob('*.json')))} schemas\n")


def render(source: Path, page: dict, pages: dict[Path, dict]) -> str:
    body = docs.expand(source, page["root"]).splitlines()
    heading = next((i for i, line in enumerate(body) if line.startswith("# ")), None)
    if heading is None:
        raise SystemExit(f"{source}: no # heading")
    title = body.pop(heading)[2:].strip()
    check_html(source, body)
    fenced = False
    for i, line in enumerate(body):
        if FENCE.match(line):
            fenced = not fenced
        elif not fenced:
            line = IMAGE.sub(lambda m: m[0] if image(source, m[2], page) else "", line)
            body[i] = LINK.sub(lambda m: f"]({link(source, m[1], pages)})", line)
    meta = ["---", f"title: {json.dumps(title)}"]
    if page.get("description"):
        meta.append(f"description: {json.dumps(page['description'])}")
    if page.get("head"):
        meta.append(f"head: {json.dumps([{'tag': 'title', 'content': page['head']}])}")
    if page["key"] in LIVE:
        meta.append(f"live: {json.dumps(LIVE[page['key']])}")
    meta += ["sidebar:", f"  order: {page['order']}"]
    if page.get("label"):
        meta.append(f"  label: {json.dumps(page['label'])}")
    return "\n".join([*meta, "---", *body]) + "\n"


def check_html(source: Path, body: list[str]) -> None:
    """No HTML tag in a page's prose: a `<title>` or `<code>` outside a code span is
    HTML to the site's Markdown, and swallows or restyles the rest of the page."""
    prose = "\n".join("" if fenced else line for line, fenced in zip(body, fences(body), strict=True))
    prose = CODE_SPAN.sub(lambda m: re.sub(r"[^\n]", " ", m[0]), prose)
    for m in HTML_TAG.finditer(prose):
        line = prose.count("\n", 0, m.start()) + 1
        raise SystemExit(
            f"{source.relative_to(ROOT)}: {m[0]} (line {line} of the page, after its quotes) is an HTML tag"
            " in the site's Markdown; put it in a code span"
        )


def fences(body: list[str]) -> list[bool]:
    """For each line, whether it is a fence or inside one."""
    inside, out = False, []
    for line in body:
        if FENCE.match(line):
            inside = not inside
            out.append(True)
        else:
            out.append(inside)
    return out


def image(source: Path, target: str, page: dict) -> bool:
    """An image of the package, copied beside the collected page at the same relative path; False when its file is missing."""
    if re.match(r"[a-z]+:", target):
        return True
    if target.startswith("/") or ".." in Path(target).parts:
        raise SystemExit(f"{source.relative_to(ROOT)}: the image {target} is not under the page's own directory")
    file = source.parent / target
    if not file.is_file():
        sys.stderr.write(f"warning: {source.relative_to(ROOT)}: no image {target}, left out\n")
        return False
    dest = page["out"].parent / target
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(file, dest)
    return True


def link(source: Path, target: str, pages: dict[Path, dict]) -> str:
    """A link to another page of the documentation becomes that page's URL."""
    if re.match(r"([a-z]+:|#|/)", target):
        return target
    path, _, anchor = target.partition("#")
    if Path(path).suffix.lower() in IMAGE_SUFFIXES:
        return target  # an image, copied beside the page by `image`
    page = pages.get((source.parent / path).resolve())
    if page is None:
        raise SystemExit(f"{source.relative_to(ROOT)}: the link to {target} names no page of the documentation")
    return page["url"] + (f"#{anchor}" if anchor else "")


def check_live(keys: set[str]) -> None:
    """Each entry of `LIVE` names a page, an example and an image that exist, and elements the manifests declare."""
    tags = {
        d["tagName"]
        for manifest in MANIFESTS
        if manifest.is_file()
        for module in json.loads(manifest.read_text())["modules"]
        for d in module.get("declarations", [])
        if d.get("tagName")
    }
    for key, figures in LIVE.items():
        if key not in keys:
            raise SystemExit(f"collect.py: LIVE names {key}, no page of the documentation")
        for f in figures:
            if "example" in f and not (ROOT / f"web/packages/elements/docs/examples/{f['example']}.ts").is_file():
                raise SystemExit(f"collect.py: LIVE[{key}] names no example {f['example']}")
            if "image" in f and not (ROOT / f["image"]).is_file():
                raise SystemExit(f"collect.py: LIVE[{key}] names no file {f['image']}")
            unknown = [t for t in f["tags"] if tags and t not in tags]
            if unknown:
                raise SystemExit(f"collect.py: LIVE[{key}] names {', '.join(unknown)}, not in the manifests")


if __name__ == "__main__":
    main()
