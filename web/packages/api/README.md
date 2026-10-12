# @contraagent/api

A typed client for the contraagent monitor's HTTP API: types generated from the
monitor's OpenAPI document, a REST client, the two live feeds, and a store that
folds a run's feed into one typed state. No UI: `@contraagent/ui` draws it.

The types are generated from the monitor's pydantic models via OpenAPI, so a
field the server removes fails your type check, not your page.

## Types

Every response and feed message has a type, with readable aliases:
`JournalRow`, `TaskRollup`, `Plan`, `Outputs`, `TaskDetail`, `StreamPage`,
`TranscriptEvent`, and so on. Fields the server may leave out are optional.

The live feeds are discriminated unions on the SSE event name, so a `switch` on
`msg.event` narrows `msg.data`:

::code{file="src/run-state.ts" from="export function reduceRun" to="// --- selectors"}

## The client

`createMonitorClient({ baseUrl })` has one typed method per JSON route
(`src/client.ts`); each throws `ApiError` on a non-2xx answer.

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
The reducer behind it, `reduceRun(state, actions)`, is pure: use it with your
own state management if you prefer. `@contraagent/ui`'s documentation shows
the store feeding its elements.
