# Live data

The elements draw what they are given; `@contraagent/api` gets it: a typed
client, the live feeds and a store that folds a run's feed into one state.

## A run's journal

The store does the data work and the element draws it:

::code{file="examples/journal.ts"}

## One transcript, tailed

`<ca-transcript>` tails a task's transcript itself when it is given `run` and
`stream`; the page decides what a reader's request means:

::code{file="examples/live-transcript.ts"}
