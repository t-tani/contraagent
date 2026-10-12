---
name: writer
description: Writes a short Japanese design note from a summary passed in a call file.
tools: Read, Write
---

1. Read the call file. `params.summary` is what the note is about.
2. Write a short note in Japanese: a `#` heading with the unit name, then one
   paragraph per point.
3. Write it to the call's `output.path` as Markdown. A linter checks it when you
   stop; fix what it reports and stop again.
