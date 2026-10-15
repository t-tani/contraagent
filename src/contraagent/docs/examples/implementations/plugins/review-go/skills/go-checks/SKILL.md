---
name: go-checks
description: How to run and read go vet on one package. Use before writing a Go review.
---

Run `go vet ./<path>`. Each line after `# <package>` is one finding:
`file:line:column: message`. Keep the file, the line and the message.
