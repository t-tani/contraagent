# Theming

Each element keeps its styles in its own shadow root, so your page's CSS cannot
break it and its CSS cannot leak into your page. What reaches it are custom
properties, in two layers:

1. **A built-in theme**, picked by `data-ca-theme="<name>"` on any ancestor
   (or on the element). It sets every colour token.
2. **A `--ca-*` property** set on any ancestor overrides one token, whatever the
   theme. A theme of your own is a set of them.

With neither, an element shows contraagent Dark.

## The built-in themes

| `data-ca-theme` | Name | Source |
|---|---|---|
| `contraagent-dark` | contraagent Dark (the default) | this package |
| `contraagent-light` | contraagent Light | this package: the hues of contraagent Dark, set for a light page |
| `github-dark` | GitHub Dark | [GitHub Primer primitives](https://github.com/primer/primitives), dark (MIT, GitHub Inc.) |
| `github-light` | GitHub Light | Primer primitives, light (MIT, GitHub Inc.) |
| `one-dark` | One Dark | [Atom One Dark](https://github.com/atom/atom/tree/master/packages/one-dark-syntax) (MIT, GitHub Inc.) |
| `nord` | Nord | [Nord](https://www.nordtheme.com) (MIT, Arctic Ice Studio and Sven Greb) |
| `high-contrast` | High contrast | Primer primitives, dark high contrast (MIT, GitHub Inc.) |

An editor theme takes its surfaces, borders and text from the editor's own
colours, its accent from the palette's accent, the statuses from its red,
yellow, green and cyan, and the code colours from its syntax colours. Where a
palette colour reads under 4.5:1 on the theme's surfaces and tints, its lightness
is raised (or lowered, on a light theme) as little as needed and its hue kept;
`src/styles/themes.ts` lists every value. High contrast keeps text at 7:1 or
more on every surface, has stronger borders and a wider focus ring, and its
status colours stay apart under protanopia, deuteranopia and tritanopia.

## Choosing a theme

In the monitor, the header's theme control changes the theme and remembers it
in this browser. `System` follows the system's colour scheme (contraagent Dark
or contraagent Light). With no choice made, the monitor shows contraagent Dark.

`<ca-monitor theme="nord">` fixes the theme of an embedded monitor; it also
takes `system`. The theme it shows is reflected as `data-ca-theme` on the
element (and on `<html>`, with `history="url"`).

For the other elements, set `data-ca-theme` on any ancestor. Importing the
package adds the themes' rules to the page's document; for elements inside a
shadow root of your own, add them there:

```ts
import { adoptThemes } from '@contraagent/ui';

adoptThemes(myShadowRoot);
```

The themes are also plain data, without the elements:
`import { THEMES, resolveTheme, themeRules } from '@contraagent/ui/themes'`.
`themeRules` writes the rules for a selector of your own, and
`themeBootScript` is a script for a page's `<head>` that sets the reader's
theme before the first paint, as the monitor's page does.

## What a colour means

A colour means one thing, on every screen and in every theme:

- **Neutral by default.** Text, totals, cost, tokens, time and every count that
  is not a count of a problem are in the text colours. A number is emphasised by
  its size and weight, not by a colour of its own.
- **A status colour marks a status, and only where it applies.** A count of a
  problem (failed attempts, tasks not started) takes its status colour above 0;
  at 0 it is neutral, with its words ("All attempts passed"). A total is never
  coloured by its worst part.
- **A status also has a shape and a word**, so it reads without colour: ✓ done,
  ✕ failed, ◌ not started, a round mark for done and a square one for failed.
- **One rule set draws every status.** An element that shows a status carries
  `data-tone` (`failed`, `attention`, `done`, `running`, `muted`; none for
  neutral), which picks its `--ca-status-*` colour and tint, and `data-mark`
  for its mark.
- **One accent** for links and the selected tab or item; the focus ring has
  its own colour and width.
- **Identity colours are small cues** (an agent task's icon and edge, the token
  bars, the timeline's bars): none of them is a status hue.

| Properties | Meaning |
|---|---|
| `--ca-backdrop`, `--ca-bg`, `--ca-card`, `--ca-panel`, `--ca-panel2`, `--ca-raise`, `--ca-well`, `--ca-track`, `--ca-line`, `--ca-line2`, `--ca-shadow` | the page, surfaces, borders and shadows |
| `--ca-text`, `--ca-text-secondary`, `--ca-text-muted` | text, from the main text to labels and units |
| `--ca-accent`, `--ca-accent-bg` | what can be clicked or is selected |
| `--ca-focus`, `--ca-focus-width` | the focus ring |
| `--ca-selection` | selected text |
| `--ca-status-failed` | failed: a task, an attempt, a check |
| `--ca-status-attention` | not failed, needs a look: not started, a usage limit near |
| `--ca-status-done` | done or passed: in marks and small chips only |
| `--ca-status-running` | running, live |
| `--ca-status-muted` | skipped, waiting, not run |
| `--ca-status-*-bg`, `--ca-tint` | the tint behind a status pill or chip: by default the status colour at `--ca-tint` |
| `--ca-agent`, `--ca-agent-bg` | identity: an agent task |
| `--ca-meter` | a bar that measures, not judges: time, usage, progress |
| `--ca-tok-input`, `--ca-tok-cache-read`, `--ca-tok-cache-write`, `--ca-tok-output` | the kinds of tokens in a bar |
| `--ca-code-*` | syntax colours in code, prompts and JSON |
| `--ca-color-scheme` | `light` or `dark`: native controls and scrollbars |
| `--ca-sans`, `--ca-mono` | the fonts |

Every property, its meaning and its value in each built-in theme are in the
site's theme reference, generated from `src/styles/themes.ts` (`TOKENS`, `THEMES`).

## A theme of your own

Set the `--ca-*` properties on an ancestor, here a class on `<body>`. Build it
the way the built-in themes are built: each text colour keeps a contrast of at
least 4.5:1 (WCAG AA) on every surface and on every status tint.

::code{file="examples/theme.css"}
