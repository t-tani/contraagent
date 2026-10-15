# Changelog fragments

Each user-visible change is one file here, which `towncrier build` turns into a
bullet of the next release in `CHANGELOG.md`.

- **Name**: `<slug>.<type>.md`, the slug in lowercase letters, digits, `-` and
  `_` (`time-boxes.added.md`); `+<slug>.<type>.md` for a fragment that names no
  topic of its own.
- **Type**, Keep a Changelog's sections: `added`, `changed`, `deprecated`,
  `removed`, `fixed`, `security`.
- **Text**: Markdown, unindented; it becomes one bullet, so a sublist or a table
  is fine. A renamed public name is written as old → new.

```
uv run towncrier create time-boxes.added.md --content "..."   # or write the file
uv run towncrier build --draft --version 0.2.0                 # preview the section
uv run towncrier build --version 0.2.0                         # at a release: writes CHANGELOG.md, removes the fragments
```
