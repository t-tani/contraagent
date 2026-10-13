# @contraagent/api

A typed client for the contraagent monitor's HTTP API: types generated from the
monitor's OpenAPI document, a REST client, the two live feeds, and a store that
folds a run's feed into one typed state. No UI: `@contraagent/ui` draws it.

The types are generated from the monitor's pydantic models via OpenAPI, so a
field the server removes fails your type check, not your page.

A `::code` line quotes a file of the package; the documentation site (`pnpm docs` in `web/`) shows the quoted lines in place. The same declarations, with their comments, are in `dist/**/*.d.ts`.

## Getting it

The package is not in the npm registry; install it from a checkout of the
repository. Every monitor also serves the client, the feeds and the store as
exports of its `/app.js` (`@contraagent/ui`'s documentation).

## Use it from a checkout

In the repository's `web/` (Node 22, pnpm through `corepack enable`):

```
pnpm install && pnpm tarballs
```

`pnpm tarballs` builds the packages and writes one `.tgz` file for each to
`web/tarballs/`. Then, in your project, with npm or pnpm:

```
npm install <checkout>/web/tarballs/contraagent-api-*.tgz
pnpm add <checkout>/web/tarballs/contraagent-api-*.tgz
```

## Types

Every response and feed message has a type, with readable aliases:
`JournalRow`, `RunSummary`, `Plan`, `Outputs`, `TaskDetail`, `StreamPage`,
`TranscriptEvent`, and so on. Fields the server may leave out are optional.
Closed vocabularies are unions: `Stop` (how an attempt ended, `JournalRow['stop']`),
`TaskState`, `ContractStatus`.

The live feeds are discriminated unions on the SSE event name, so a `switch` on
`msg.event` narrows `msg.data`:

::code{file="src/run-state.ts" from="export function reduceRun" to="// --- selectors"}

## The client

`createMonitorClient({ baseUrl })` has one typed method per JSON route
(`src/client.ts`); each throws `ApiError` when it gets no JSON answer: its
`failure` is `network`, `status`, `empty` or `not-json` (an HTML page from a
server without the API), and its message states the URL and the cause.

## The live feeds

- `openRunFeed(run, panels, handlers)`: the run, live. On every (re)connect the
  server replays the whole journal and then sends `ready`; every message after
  `ready` is new.
- `openStreamFeed(run, key, handlers)`: one transcript, tailed: the tail page
  first, then only what is new.

Each returns a function that closes it.

## The store

`MonitorStore` keeps the run list fresh, opens the selected run's feed, folds
its messages into one `RunState`, and tells subscribers. It knows nothing of
any UI framework: a Lit controller, a React hook or plain code subscribe alike.
Its snapshot's `error` is the `ApiError` of the last request for the title or
the run list that got no answer (also written to the console), and
`runsLoaded` says the run list has been answered.
The reducer behind it, `reduceRun(state, actions)`, is pure: use it with your
own state management if you prefer. `@contraagent/ui`'s documentation shows
the store feeding its elements.

## Tasks and their outcomes

A task is one task key. `deriveRun(journal, plan)` gives what every view counts
and lists about the run's tasks, computed once per state (the same `journal` and
`plan` objects give the same result):

- `outcomes` and `rows`: every task of the run, the plan joined with the
  journal, with its outcome (`done`, `recovered`, `failed`, `not_started`,
  `running`, `waiting`, `skipped`);
- `counts`: tasks by outcome, `doneTotal` (done and recovered: "N of M tasks
  done") and `finished` (done, recovered and skipped);
- `problems`: failed tasks with the tasks they stopped, tasks not started for a
  reason of their own, and recovered tasks;
- `kinds` and `tries`.

`latestTask(rows)` is the task a page opens by default. A refusal before launch
(`invalid_input`) is not a try: a task refused and then done is `done`, not
`recovered`.
