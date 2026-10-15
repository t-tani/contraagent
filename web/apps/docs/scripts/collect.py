"""Each package's documentation, as pages of this site.

    uv run python web/apps/docs/scripts/collect.py

Writes every page an index lists into src/content/docs/<section>/ (not
committed): the title from the page's heading, the order and description from
its index, each `::code{...}` expanded by `contraagent.docs.expand` (the one
implementation `contraagent docs` uses too), each link pointed at the page it
names. A quote or a link that does not resolve stops it.
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

#: Each package's index, the directory its quotes are relative to, and the site section it becomes.
SECTIONS = [
    (docs.INDEX, docs.DIR, "python"),
    (ROOT / "web/packages/api/README.md", ROOT / "web/packages/api", "node/api"),
    (ROOT / "web/packages/ui/README.md", ROOT / "web/packages/ui", "node/ui"),
    (ROOT / "web/packages/elements/README.md", ROOT / "web/packages/elements", "node/elements"),
]
LINK = re.compile(r"\]\(([^)\s]+)\)")
FENCE = re.compile(r"^\s*```")


def main() -> None:
    pages: dict[Path, dict] = {}
    for index, root, section in SECTIONS:
        out = CONTENT / section / "index.md"
        pages[index.resolve()] = {"root": root, "url": f"/{section}/", "out": out, "order": 0, "label": "Overview"}
        for order, entry in enumerate(docs.entries(index), 1):
            pages[entry.path] = {
                "root": root,
                "url": f"/{section}/{entry.name}/",
                "out": CONTENT / section / f"{entry.name}.md",
                "order": order,
                "description": entry.summary,
            }
    for _, _, section in SECTIONS:
        shutil.rmtree(CONTENT / section, ignore_errors=True)
    for source, page in pages.items():
        page["out"].parent.mkdir(parents=True, exist_ok=True)
        page["out"].write_text(render(source, page, pages))
    sys.stdout.write(f"collected {len(pages)} pages\n")


def render(source: Path, page: dict, pages: dict[Path, dict]) -> str:
    body = docs.expand(source, page["root"]).splitlines()
    heading = next((i for i, line in enumerate(body) if line.startswith("# ")), None)
    if heading is None:
        raise SystemExit(f"{source}: no # heading")
    title = body.pop(heading)[2:].strip()
    fenced = False
    for i, line in enumerate(body):
        if FENCE.match(line):
            fenced = not fenced
        elif not fenced:
            body[i] = LINK.sub(lambda m: f"]({link(source, m[1], pages)})", line)
    meta = ["---", f"title: {json.dumps(title)}"]
    if page.get("description"):
        meta.append(f"description: {json.dumps(page['description'])}")
    meta += ["sidebar:", f"  order: {page['order']}"]
    if page.get("label"):
        meta.append(f"  label: {json.dumps(page['label'])}")
    return "\n".join([*meta, "---", *body]) + "\n"


def link(source: Path, target: str, pages: dict[Path, dict]) -> str:
    """A link to another page of the documentation becomes that page's URL."""
    if re.match(r"([a-z]+:|#|/)", target):
        return target
    path, _, anchor = target.partition("#")
    page = pages.get((source.parent / path).resolve())
    if page is None:
        raise SystemExit(f"{source.relative_to(ROOT)}: the link to {target} names no page of the documentation")
    return page["url"] + (f"#{anchor}" if anchor else "")


if __name__ == "__main__":
    main()
