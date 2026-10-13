# Embed the monitor

`<ca-monitor>` is the complete monitor: header, run switcher, tabs, filters,
views and notifications. It holds the data (a `MonitorStore`) and the route.
Its attributes (`base-url`, `history`, `run`, `locale`, `theme`) are described in
`custom-elements.json`. `history="url"` suits a page that is the monitor;
inside an application with its own router, use `history="memory"`.

## What the host page keeps

With `history="memory"`, the monitor leaves the page to its host:

| | `history="url"` (the monitor is the page) | `history="memory"` (embedded) |
|---|---|---|
| Route (run, tab, filters) | the URL's query; Back and Forward | the element; the URL and the history are the host's |
| Scroll positions, open sections | the page's history entry, under `contraagent` | the element |
| `document.title` | "<title> monitor" | not written |
| `<html lang>`, `<html data-ca-theme>` | follow the monitor's language and theme | not written; `lang` and `data-ca-theme` are set on `<ca-monitor>` |
| Single-key shortcuts | anywhere in the page (`shortcuts="page"`) | only while the focus is inside the monitor (`shortcuts="element"`) |
| The monitor's listeners on `document` and `window` | `keydown`, `popstate`, `pagehide` | none |

The single-key shortcuts are 1 to 9 (the tabs), `r` (the run switcher) and `/`
(the filter). In every scope they never take a key typed into a text field
(`input`, `select`, `textarea`, an editable element), a key pressed with Ctrl,
Alt or Meta, or a key a listener of the host already handled with
`preventDefault()`. `shortcuts="off"` turns them off, and the tab bar then
shows no key hint; `shortcuts="page"` gives an embedded monitor the whole page.

While the run switcher or the theme menu is open, a click elsewhere in the page
closes it. The monitor listens on the document for that click only while one
of them is open, and neither stops nor prevents it.

Two monitors on one page each keep their own route, scroll positions, open
sections and shortcuts. They share what is one per page:

- the language: Lit Localize has one locale per page, so `locale` on one
  monitor, or its language switch, changes the other's too;
- the reader's choices of language and theme, remembered in `localStorage`
  (`contraagent:locale`, `contraagent:theme`), as the monitor's switches do;
- the themes' rules, added once to the document's adopted style sheets; they
  match only `[data-ca-theme]`, so the host's own elements are not restyled;
- Lit Localize's `lit-localize-status` event on `window`, which every element
  listens for to change its language.

`e2e/embed.spec.ts` (in the repository's `web/`) checks this on a host page
with its own title, text field and single-key shortcuts, and two monitors.

## Without a build step

::code{file="examples/embed.html"}

A page on another origin can only import `/app.js` and read the API if the
monitor names that origin: `contraagent monitor --cors-origin http://localhost:8000`.

## In an application

Import the package once; the elements register themselves. When it connects,
`<ca-monitor>` sets up the languages (`configureLocales()`) and adds the
themes' rules to its document (`adoptThemes(this.ownerDocument)`); a page
that shows other elements without a monitor calls them itself (`adoptThemes`
is in `@contraagent/elements/themes`). Give `<ca-monitor>` a box with a height: it fills it and scrolls inside it. In React
19, Vue, Svelte, Astro or plain HTML, `<ca-monitor>` is an ordinary element.
Properties without an attribute take objects and arrays: set them from script
(`el.rows = [...]`), or with a property binding in your framework (`.rows=${...}`
in Lit, `rows={...}` in React 19).
