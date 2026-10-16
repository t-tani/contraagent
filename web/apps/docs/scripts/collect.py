"""Each package's documentation, as pages of this site.

    uv run python web/apps/docs/scripts/collect.py

Writes every page an index lists into src/content/docs/<section>/ (not
committed): the title from the page's heading, the order and description from
its index, each `::code{...}` expanded by `contraagent._internal.docs.expand` (the one
implementation `contraagent docs` uses too), each link pointed at the page it
names. A quote, a link or an image that does not resolve stops it, and so does
an HTML tag in a page's prose (outside code), which the site would render.

A paragraph under a line `<!-- not on the site -->` is for readers of the
package's files only (a pointer to the site): the site leaves it out.

The site shows the web packages' elements live, not as pictures. `LIVE` is the
site's own part of those pages: for each, the live elements it shows (`demo`, a
`ca-*` view fed with the demo run; `example`, an example of
`@contraagent/elements`), each in place of the screenshot it names (`at`), or
under the title. Such a page becomes MDX, each live element a
`<LiveFigure>` (src/components/LiveFigure.astro). A screenshot of an element
(`images/` or `docs/images/` in a web package) with no live element in its
place, a topic of `@contraagent/elements` with none at all (but those in
`NO_ELEMENT`), and an `at` that names no image of its page stop the collector.
Any other image is copied beside the collected page, so its relative link still
holds.

The JSON Schemas of the Python package's files (`contraagent/docs/schemas/`) go
into public/schemas/, served as they are.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path

from contraagent._internal import docs

ROOT = Path(__file__).resolve().parents[4]
CONTENT = Path(__file__).resolve().parents[1] / "src" / "content" / "docs"
COMPONENTS = Path(__file__).resolve().parents[1] / "src" / "components"
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
#: The line before a paragraph the site leaves out.
NOT_ON_SITE = "<!-- not on the site -->"
MANIFESTS = [ROOT / "web/packages/ui/custom-elements.json", ROOT / "web/packages/elements/custom-elements.json"]
#: The sections whose screenshots are of elements, and where they live.
ELEMENT_SECTIONS = ("node/ui", "node/elements")
SCREENSHOT = re.compile(r"(docs/)?images/")
#: Topics of @contraagent/elements about no one element.
NO_ELEMENT = {"node/elements/strings"}


def demo(tag: str, props: dict[str, str], **more: object) -> dict:
    """A `ca-*` view fed with the demo run (src/fixtures/demo-run.json): `props` maps its
    properties to the fixture's keys (`=<json>`: that value; `@client`: a client of the
    demo export, public/demo/data/); `attrs` are its attributes; `height` is the element's own (one
    that fills the box it is given); `page=True`: a whole page, which fills its frame; `scroll`: the most a long list's frame
    grows to before it scrolls; `full`: a page that shows the element alone, linked under it (Demo.astro)."""
    return {"demo": tag, "props": props, "tags": [tag], **more}


def example(name: str, *tags: str, **more: object) -> dict:
    """`@contraagent/elements`' example `docs/examples/<name>.ts`, mounted; `tags` are the elements it shows;
    `page=True`: the example builds a whole page, which fills its frame (Example.astro)."""
    return {"example": name, "tags": list(tags), **more}


RUN = {"plan": "plan", "journal": "journal", "run": "run"}
#: The most a long list's frame grows to before it scrolls.
LONG = "640px"
MONITOR = demo(
    "ca-monitor",
    {},
    attrs={"export": "/demo/data/", "history": "memory", "shortcuts": "element", "theme": "contraagent-light"},
    theme="contraagent-light",
    height="720px",
    page=True,
    full="/demo/monitor/",
)

#: A page (section/name) and its live elements, in order; `at`: the screenshot each takes the place of.
LIVE: dict[str, list[dict]] = {
    "node/ui/index": [
        {**MONITOR, "at": "docs/images/monitor.webp"},
        demo("ca-pipeline-graph", RUN, at="docs/images/pipeline-graph.webp"),
        demo(
            "ca-task-view",
            {**RUN, "client": "@client", "live": "=false", "taskKey": '="write_note-alpha"'},
            at="docs/images/task-view.webp",
        ),
        demo(
            "ca-journal-table",
            {"rows": "journal", "plan": "plan", "kind": '="summarize"'},
            at="docs/images/journal-table.webp",
        ),
        demo("ca-task-table", {**RUN, "kind": '="summarize"'}, at="docs/images/task-table.webp"),
        demo("ca-contracts", {**RUN, "outputs": "outputs"}, at="docs/images/contracts.webp", scroll=LONG),
        demo("ca-definitions", {**RUN, "client": "@client", "live": "=false"}, at="docs/images/definitions.webp"),
        demo("ca-kpis", {"journal": "journal", "plan": "plan"}, at="docs/images/kpis.webp"),
        demo("ca-timeline", RUN, at="docs/images/timeline.webp"),
    ],
    "node/ui/embed": [MONITOR],
    "node/ui/live-data": [demo("ca-journal-table", {"rows": "journal", "plan": "plan"}, scroll=LONG)],
    "node/ui/events": [demo("ca-pipeline-graph", RUN)],
    "node/ui/theming": [
        demo("ca-kpis", {"journal": "journal", "plan": "plan"}, caption="contraagent-dark"),
        demo("ca-kpis", {"journal": "journal", "plan": "plan"}, theme="github-light", caption="github-light"),
        demo(
            "ca-kpis",
            {"journal": "journal", "plan": "plan"},
            theme="contraagent-light",
            custom="solarized-light",
            caption="solarized-light, a theme of one's own (@contraagent/elements docs/examples/theme.css)",
        ),
    ],
    "node/elements/index": [example("ci-pipeline", "cae-segmented", "cae-stat-tiles", "cae-data-table", "cae-layered-graph", page=True)],
    "node/elements/primitives": [
        example("status", at="images/primitives.webp"),
        example("segmented", "cae-segmented", at="images/primitives.webp"),
    ],
    "node/elements/theming": [
        example("ci-pipeline", at="images/theming-dark.webp", page=True, caption="contraagent-dark"),
        example(
            "tiles",
            "cae-stat-tiles",
            at="images/theming-dark.webp",
            theme="contraagent-light",
            custom="solarized-light",
            caption="solarized-light, a theme of one's own (docs/examples/theme.css)",
        ),
    ],
    "node/elements/data-table": [example("data-table", "cae-data-table", at="images/data-table.webp")],
    "node/elements/graph": [example("graph", "cae-layered-graph", at="images/graph.webp")],
    "node/elements/matrix": [example("matrix", "cae-mark-matrix", at="images/matrix.webp")],
    "node/elements/tiles": [example("tiles", "cae-stat-tiles", at="images/tiles.webp")],
    "node/elements/lanes": [example("lanes", "cae-lanes", at="images/lanes.webp")],
    "node/elements/charts": [
        example("charts", "cae-column-chart", "cae-line-chart", "cae-heatmap", "cae-bar-chart", at="images/charts.webp")
    ],
    "node/elements/check-table": [example("check-table", "cae-check-table", at="images/check-table.webp")],
    "node/elements/transcript": [example("transcript", "cae-transcript", at="images/transcript.webp")],
    "node/elements/page": [example("ci-pipeline", at="images/page.webp", page=True)],
}


def main() -> None:
    pages: dict[Path, dict] = {}
    for index, root, section, package in SECTIONS:
        pages[index.resolve()] = {
            "root": root,
            "url": f"/{section}/",
            "out": CONTENT / section / "index.md",
            "key": f"{section}/index",
            "section": section,
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
                "section": section,
                "order": order,
                "description": entry.summary,
                # Two packages have a "Theming": a web package's tab names the package.
                "head": None if section == "python" else f"{entry.title} | {package}",
            }
    check_live({page["key"] for page in pages.values()})
    for _, _, section, _ in SECTIONS:
        shutil.rmtree(CONTENT / section, ignore_errors=True)
    for source, page in pages.items():
        if page["key"] in LIVE:
            page["out"] = page["out"].with_suffix(".mdx")
        page["out"].parent.mkdir(parents=True, exist_ok=True)
        page["out"].write_text(render(source, page, pages), encoding="utf-8", newline="\n")
    shutil.rmtree(SCHEMAS, ignore_errors=True)
    shutil.copytree(docs.DIR / "schemas", SCHEMAS)
    sys.stdout.write(f"collected {len(pages)} pages and {len(list(SCHEMAS.glob('*.json')))} schemas\n")


def render(source: Path, page: dict, pages: dict[Path, dict]) -> str:
    body = docs.expand(source, page["root"]).splitlines()
    heading = next((i for i, line in enumerate(body) if line.startswith("# ")), None)
    if heading is None:
        raise SystemExit(f"{source}: no # heading")
    title = body.pop(heading)[2:].strip()
    body = site_only(body)
    check_html(source, body)
    live = LIVE.get(page["key"], [])
    placed: dict[str, list[int]] = {}
    for i, f in enumerate(live):
        placed.setdefault(f.get("at", ""), []).append(i)
    out: list[str] = []
    for line, fenced in zip(body, fences(body), strict=True):
        if fenced:
            out.append(line)
            continue
        shot = IMAGE.fullmatch(line.strip())
        if shot and shot[2] in placed:
            out += [f"\0{i}" for i in placed.pop(shot[2])]
            continue
        for m in IMAGE.finditer(line):
            image(source, m[2], page)
        out.append(LINK.sub(lambda m: f"]({link(source, m[1], pages)})", line))
    placed.pop("", None)
    if placed:
        raise SystemExit(f"collect.py: LIVE[{page['key']}] puts a live element at {', '.join(placed)}, no image of the page")
    meta = ["---", f"title: {json.dumps(title)}"]
    if page.get("description"):
        meta.append(f"description: {json.dumps(page['description'])}")
    if page.get("head"):
        meta.append(f"head: {json.dumps([{'tag': 'title', 'content': page['head']}])}")
    if live:
        meta.append(f"live: {json.dumps(live)}")
    meta += ["sidebar:", f"  order: {page['order']}"]
    if page.get("label"):
        meta.append(f"  label: {json.dumps(page['label'])}")
    meta.append("---")
    if not live:
        return "\n".join([*meta, *out]) + "\n"
    component = Path(os.path.relpath(COMPONENTS / "LiveFigure.astro", page["out"].parent)).as_posix()
    top = [f"\0{i}" for i, f in enumerate(live) if not f.get("at")]
    text = mdx_escape("\n".join([*top, *([""] if top else []), *out]))
    text = re.sub(r"\0(\d+)", lambda m: f"<LiveFigure figure={{{json.dumps(live[int(m[1])])}}} />", text)
    return "\n".join([*meta, "", f"import LiveFigure from '{component}';", "", text]) + "\n"


def mdx_escape(text: str) -> str:
    """Markdown as MDX reads it the same: outside code, `{`, `}` and `<` are text."""
    lines = text.split("\n")
    parts: list[str] = []
    block: list[str] = []

    def prose() -> None:
        joined = "\n".join(block)
        joined = re.sub(
            r"(`+)[\s\S]+?\1|[{}<]",
            lambda m: m[0] if m[0].startswith("`") else {"{": r"\{", "}": r"\}", "<": "&lt;"}[m[0]],
            joined,
        )
        parts.append(joined)
        block.clear()

    for line, fenced in zip(lines, fences(lines), strict=True):
        if fenced:
            if block:
                prose()
            parts.append(line)
        else:
            block.append(line)
    if block:
        prose()
    return "\n".join(parts)


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


def site_only(body: list[str]) -> list[str]:
    """The page without each `<!-- not on the site -->` line and the paragraph under it."""
    out: list[str] = []
    skipping = False
    for line, fenced in zip(body, fences(body), strict=True):
        if not fenced and line.strip() == NOT_ON_SITE:
            skipping = True
        elif skipping and not line.strip():
            skipping = False
        elif not skipping:
            out.append(line)
    return out


def image(source: Path, target: str, page: dict) -> None:
    """An image the site keeps, copied beside the collected page at the same relative path."""
    if re.match(r"[a-z]+:", target):
        return
    if page["section"] in ELEMENT_SECTIONS and SCREENSHOT.match(target):
        raise SystemExit(
            f"{source.relative_to(ROOT)}: the screenshot {target} has no live element in its place on the site"
            f" (collect.py, LIVE[{page['key']!r}], at={target!r})"
        )
    if target.startswith("/") or ".." in Path(target).parts:
        raise SystemExit(f"{source.relative_to(ROOT)}: the image {target} is not under the page's own directory")
    file = source.parent / target
    if not file.is_file():
        raise SystemExit(f"{source.relative_to(ROOT)}: the image {target} names no file")
    dest = page["out"].parent / target
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(file, dest)


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
    """Each topic of @contraagent/elements has live elements (but `NO_ELEMENT`); each entry of
    `LIVE` names a page and an example that exist, and elements the manifests declare."""
    missing = sorted(k for k in keys if k.startswith("node/elements/") and k not in LIVE and k not in NO_ELEMENT)
    if missing:
        raise SystemExit(f"collect.py: {', '.join(missing)} shows no element live; add it to LIVE (or to NO_ELEMENT)")
    tags = {
        d["tagName"]
        for manifest in MANIFESTS
        if manifest.is_file()
        for module in json.loads(manifest.read_text(encoding="utf-8"))["modules"]
        for d in module.get("declarations", [])
        if d.get("tagName")
    }
    for key, figures in LIVE.items():
        if key not in keys:
            raise SystemExit(f"collect.py: LIVE names {key}, no page of the documentation")
        for f in figures:
            if "example" in f and not (ROOT / f"web/packages/elements/docs/examples/{f['example']}.ts").is_file():
                raise SystemExit(f"collect.py: LIVE[{key}] names no example {f['example']}")
            unknown = [t for t in f["tags"] if tags and t not in tags]
            if unknown:
                raise SystemExit(f"collect.py: LIVE[{key}] names {', '.join(unknown)}, not in the manifests")


if __name__ == "__main__":
    main()
