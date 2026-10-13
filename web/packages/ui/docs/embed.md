# Embed the monitor

`<ca-monitor>` is the complete monitor: header, run switcher, tabs, filters,
views and notifications. It holds the data (a `MonitorStore`) and the route.
Its attributes (`base-url`, `history`, `run`, `locale`, `theme`) are described in
`custom-elements.json`. `history="url"` suits a page that is the monitor;
inside an application with its own router, use `history="memory"`.

## Without a build step

::code{file="examples/embed.html"}

A page on another origin can only import `/app.js` and read the API if the
monitor names that origin: `contraagent-monitor --cors-origin http://localhost:8000`.

## In an application

Import the package once; the elements register themselves. Give
`<ca-monitor>` a box with a height: it fills it and scrolls inside it. In React
19, Vue, Svelte, Astro or plain HTML, `<ca-monitor>` is an ordinary element.
Properties without an attribute take objects and arrays: set them from script
(`el.rows = [...]`), or with a property binding in your framework (`.rows=${...}`
in Lit, `rows={...}` in React 19).
