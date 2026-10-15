---
name: python-checks
description: How to run and read ruff on one module. Use before writing a Python review.
---

Run `ruff check <path> --output-format concise`. Each line is one finding:
`path:line:column: code message`. Keep the code and the message; drop the column.
