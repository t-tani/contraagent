# Theming

Each element keeps its styles in its own shadow root, so your page's CSS cannot
break it and its CSS cannot leak into your page. What reaches it are the
`--ca-*` custom properties:

1. **A built-in theme**, picked by `data-ca-theme="<name>"` on any ancestor
   (or on the element), sets every colour property on that element. The
   elements inside it read them, and so does your page's own CSS.
2. **A `--ca-*` property of your own** wins over the theme when it is set on
   the element that carries `data-ca-theme` or on an element inside it. A theme
   of your own is a set of them.

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
`src/themes/data.ts` lists every value. High contrast keeps text at 7:1 or
more on every surface, has stronger borders and a wider focus ring, and its
status colours stay apart under protanopia, deuteranopia and tritanopia.

## Choosing a theme

Set `data-ca-theme` on any ancestor. The rules that apply it are a stylesheet
that a document (or a shadow root) adopts once: add it to the page's document,
and to a shadow root of your own that holds the elements and sets
`data-ca-theme` inside it. No import adopts it; `<ca-monitor>` of
`@contraagent/ui` adopts it for its document when it connects.

```ts
import { adoptThemes } from '@contraagent/elements/themes';

adoptThemes(document);
adoptThemes(myShadowRoot);
```

The themes are also plain data: `THEMES`, `resolveTheme` and `themeRules` in
`@contraagent/elements/themes`. `themeRules` writes the rules for a selector of
your own, and `themeBootScript` is a script for a page's `<head>` that sets the
reader's theme before the first paint, as the monitor's page does.
`preferredTheme` and `rememberTheme` keep the reader's choice in this browser;
`system` follows the system's colour scheme (contraagent Dark or contraagent
Light).

## Use the theme in your own page

The theme's properties have the same names in your page as in the elements, so
your page and the elements show one theme. Here `<html data-ca-theme="nord">`
picks it, and the page's CSS reads it:

::code{file="examples/page.css"}

A theme sets each property that has a value per theme: the colours,
`--ca-tint`, `--ca-focus-width` and `--ca-color-scheme`. Its selector has no specificity,
so any rule of your page that sets a `--ca-*` property wins over it:

::code{file="../src/themes/data.ts" from="/** A theme's selector on a page" to="/**"}

The tints (`--ca-accent-bg`, `--ca-status-*-bg`, `--ca-agent-bg`), the type
scale and the corners have one default for every theme; that default exists only
inside the elements, unless your page sets the property.

## What a colour means

A colour means one thing, on every screen and in every theme:

- **Neutral by default.** Text, totals, cost, tokens, time and every count that
  is not a count of a problem are in the text colours. A number is emphasised by
  its size and weight, not by a colour of its own.
- **A status colour marks a status, and only where it applies.** A count of a
  problem (failed attempts, tasks not started) takes its status colour above 0;
  at 0 it is neutral, with its words ("All attempts done"). A total is never
  coloured by its worst part.
- **A status also has a shape and a word**, so it reads without colour: ✓ done,
  ✕ failed, ◌ not started, a round mark for done and a square one for failed.
- **One rule set draws every status.** An element that shows a status carries
  `data-tone`, its tone (`failed`, `attention`, `done`, `running`, `muted`; none
  for `neutral`), which picks its `--ca-status-*` colour and tint, and
  `data-mark` for its mark. The primitives set both
  ([Primitives](primitives.md)).
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
| `--ca-series-1` to `--ca-series-6` | the series of a chart, in a fixed order; never a status, and each series also named in words |
| `--ca-code-*` | syntax colours in code, prompts and JSON |
| `--ca-color-scheme` | `light` or `dark`: native controls and scrollbars |
| `--ca-sans`, `--ca-mono` | the fonts |
| `--ca-font-size-xs` to `--ca-font-size-2xl` | the type scale |
| `--ca-radius-sm`, `--ca-radius-md`, `--ca-radius-lg`, `--ca-radius-pill` | the corners |

Every property, its meaning and its value in each built-in theme are in the
site's theme reference, generated from `src/themes/tokens-list.ts` (`TOKENS`),
`src/themes/token-meanings.ts` (`TOKEN_MEANINGS`)
and `src/themes/data.ts` (`THEMES`).

## Type and corners

The type and radius scale is the same in every theme: no theme sets it, and
each step has a default. A `--ca-*` property on an ancestor changes a step for
every element under it.

::code{file="../src/themes/tokens-list.ts" from="{ name: 'font-size-xs'" to="];"}

## A theme of your own

Set the `--ca-*` properties on an element, here with a class: on the element
that carries `data-ca-theme`, or on one inside it (on `<body>` under
`<html data-ca-theme>`). Build it
the way the built-in themes are built: each text colour keeps a contrast of at
least 4.5:1 (WCAG AA) on every surface and on every status tint.

::code{file="examples/theme.css"}
