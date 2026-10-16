# Code

`<cae-code>` shows a text as code: highlighted by its language, each line
numbered, some lines marked, with a switch between long lines wrapped and
scrolled sideways and a button that copies the whole text. Register it with
`@contraagent/elements/code/define`; the element, the tokenizer it is drawn with
and the languages it reads are in `@contraagent/elements/code`.

<!-- not on the site -->
Live on this topic's page of the documentation site (`pnpm run docs` in `web/`).

::code{file="examples/code.ts"}

## The text

`code` is the text and `language` its language: a name of `LANGUAGES`, another
name of one (`py`, `ts`, `sh`, `yml`) or a file name (`src/main.rs`); any other
is shown as plain text. `start` is the number of the first line (1), and
`highlight` marks lines in those numbers: a number for one line, a pair for the
lines from the first to the last. A marked line has a bar beside its number and
a tint. `path` names the file in the header; `label` names the lines to a screen
reader (default: the path).

A long text costs time to draw, so the element shows at most `maxLines` lines
(5,000) and `maxCharacters` characters (500,000), cut at the end of a line, and
says under them how many lines the text has (`strings.cut`). The copy button
copies the whole text all the same.

## Highlighting

The highlighter is a small tokenizer of the package: each language is a few
regular expressions and its words, so it needs no library and no request. It
reads Python, JSON, JavaScript, TypeScript, C, C++, Java, Go, Rust, shell, TOML
(and INI), YAML, SQL, XML (and HTML and SVG) and diffs. It marks comments,
strings, numbers, keywords, constants, built-in names, the names a function or a
type is given where it is defined, and a language's own parts (keys, tags,
attributes, added and removed lines); it does not parse, so a rare construct may
take the colour of a simpler one. `tokenize(code, language)` returns the tokens,
`highlight(code, language)` escaped HTML; markdown's code blocks use the same
(`@contraagent/elements/markdown`). The colours are the theme's `--ca-code-*`
tokens ([Theming](theming.md)).

::code{file="../src/code/highlight.ts" from="/** What a token is" to="/** The languages highlighted"}

## Reading it

The lines are one tab stop that scrolls with the arrow keys. The numbers are
drawn beside the lines and are not part of a selection, so selected lines copy
without them. `wrap` wraps long lines at first; the reader's switch
(`strings.wrap`) changes it.

## Look

`--cae-code-max-height` sets the most the lines grow to before they scroll (70vh).
The parts are `header`, `code` and `cut`.
