# Embed the monitor

`<ca-monitor>` is the complete monitor: header, run switcher, tabs, filters,
views and notifications. It holds the data (a `MonitorStore`) and the view route.
Its attributes (`base-url`, `export`, `history`, `shortcuts`, `run`, `locale`, `theme`) are described in
`custom-elements.json`. `history="url"` suits a page that is the monitor;
inside an application that manages its own URL, use `history="memory"`.

## What the host page keeps

With `history="memory"`, the monitor leaves the page to its host:

| | `history="url"` (the monitor is the page) | `history="memory"` (embedded) |
|---|---|---|
| View route (run, tab, filters) | the URL's query; Back and Forward | the element; the URL and the history are the host's |
| Scroll positions, open sections | the page's history entry, under `contraagent` | the element |
| `document.title` | `<title> monitor` | not written |
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
closes it (for the theme menu, a press of the pointer). The monitor listens on the
document for that event only while one of them is open, and neither stops nor
prevents it.

Two monitors on one page each keep their own view route, scroll positions, open
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

## Connection

`base-url` names the monitor server, such as `http://127.0.0.1:8787`; unset,
it is the page's own origin. Every attribute takes effect whenever it is set,
as an attribute or a property, before or after the element connects or the
package loads:

| Attribute | A change after connecting |
|---|---|
| `base-url` | closes the old server's feeds and reads the new server: the run named by `run`, else its newest run |
| `history` | `memory` keeps the view route shown; `url` takes the address bar's |
| `run` | opens that run |
| `locale`, `theme`, `shortcuts` | show at once |

A request to the API that gets no JSON answer is shown above the view, with
its URL and its cause, and written to the console with `console.error`; the
monitor then never shows "No runs yet". The causes (`ApiError.failure` in
`@contraagent/api`):

| Cause | Typical reason |
|---|---|
| the response is HTML, not JSON | `base-url` names a server without the API, such as a development server that answers every path with the page (`index.html`) |
| the response is not JSON | the server at `base-url` answers with an empty body or with text |
| the response status is 404 | `base-url` names a server, or a path on it, without the API |
| network error, no response | the monitor server is not running, or it does not allow the page's origin (`--cors-origin`, below) |

The run list (`/api/runs`) is asked for every 5 seconds, and the title and the
custom views (`/api/info`) with it until they arrive, so a server that starts
later is read when it answers, and the message goes.

## An export, with no server

`export` names an export's `data/` directory (`contraagent monitor export`) in
place of a server: `<ca-monitor export="data/">`, relative to the page or
absolute; set, it outranks `base-url`. The monitor then makes no request to an API
and opens no feed: it reads the export's files, and its header shows when the
export was written in place of the connection. An export holds no transcripts and no processes.

## Without a build step

::code{file="examples/embed.html"}

A page on another origin can only import `/app.js` and read the API if the
monitor names that origin: `contraagent monitor --cors-origin http://localhost:8000`.

## In an application

A Vite application: the page holds `<ca-monitor>` in a box, and `src/main.ts`
imports the package and sets the monitor's `base-url`.

::code{file="examples/vite/index.html"}

::code{file="examples/vite/main.ts"}

A page served by Vite answers an unknown path such as `/api/runs` with its own
`index.html`: a monitor there without `base-url` shows "No monitor API at
http://localhost:5173/api/info: the response is HTML, not JSON" (Connection,
above).

Import the package once; the elements register themselves. When it connects,
`<ca-monitor>` sets up the languages (`configureLocales()`) and adds the
themes' rules to its document (`adoptThemes(this.ownerDocument)`); a page
that shows other elements without a monitor calls them itself (`adoptThemes`
is in `@contraagent/elements/themes`). Give `<ca-monitor>` a box with a height: it fills it and scrolls inside it.
It lays itself out by the box's width, not the window's: in a narrow box the
header wraps and the tab list scrolls sideways. In React
19, Vue, Svelte, Astro or plain HTML, `<ca-monitor>` is an ordinary element.
Properties without an attribute take objects and arrays: set them from script
(`el.rows = [...]`), or with a property binding in your framework (`.rows=${...}`
in Lit, `rows={...}` in React 19).
