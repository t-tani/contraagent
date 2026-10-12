---
name: write-output
description: How to write a task's output file so it passes its checks. Use whenever you are about to write the output file named in a call file.
---

# Writing the output file

- `output.format` "json": the file is a single JSON document matching `output.json_schema`.
  No markdown, no code fences, no comments, no trailing commas.
- Field names and types are exactly those in the schema. Do not add fields; do not rename them.
- A list field is always a list, even with one element or none.
- Copy identifiers (`unit`) from the call file, never from memory.
- Write the file once, complete. A half-written file is checked as written.
- If a hook reports errors, they name the field (or the linter rule) and what was wrong.
  Fix that; do not redo the analysis.
