# Events and routing

## Events

An element never changes what is shown on its own. It sends an event saying
what the reader asked for; its host decides. The monitor changes its route;
another page might open its own view, or ignore it. Each event crosses shadow
roots and all but `ca-rounds` bubble, so you can listen on any ancestor, and
each is typed in `HTMLElementEventMap`:

::code{file="../src/core/events.ts" from="export interface OpenTaskDetail" to="declare global"}

```ts
document.addEventListener('ca-open-task', (e) => {
  e.detail.key; // string: typed, no cast
});
```

## The route

`<ca-monitor>` keeps one typed value for where the reader is, and mirrors it in
the URL (or in memory, with `history="memory"`):

::code{file="../src/core/route.ts" from="export interface Route" to="export type RoutePatch"}

Moving to another place (a tab, a task, a view, a round, a definition, a run)
pushes a history entry, so Back returns. Changing a filter replaces the entry,
so typing does not fill the history.

## The reader's place

What the URL does not say is kept in the history entry itself
(`history.state`, under one key, merged with whatever a host's router keeps
there): how far each list is scrolled and which cards are open. Back, Forward
and a reload return to it; a new place starts at the top. Restoring waits until
the content, which arrives over the network, is tall enough to scroll to the
remembered position. Tool cards opened in a transcript are kept for the browser
tab, since one transcript is shown on several entries.
