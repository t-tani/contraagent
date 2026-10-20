# Scheduling benchmark: main (eb00a849)

contraagent 0.6.2 on Python 3.12.9, 20 seeds, one minute of agent work run in 0.2 s. Written by `benchmarks/schedule.py`, whose docstring says what each figure means. Minutes of agent work, the median over the seeds; `worst` is the largest makespan.

| scenario | run | makespan | worst | idle slot time | deferred | done by deadline | cost after deadline (USD) | would fit |
|---|---|---|---|---|---|---|---|---|
| demo | first | 36.31 | 52.93 | 15.82 | 0.0 | - | - | - |
| demo | second | 39.14 | 51.68 | 20.24 | 0.0 | - | - | - |
| demo-one-review | first | 35.81 | 55.62 | 11.79 | 0.0 | - | - | - |
| demo-one-review | second | 36.84 | 56.54 | 12.85 | 0.0 | - | - | - |
| demo-loop | first | 45.82 | 61.92 | 21.71 | 0.0 | - | - | - |
| demo-loop | second | 45.98 | 59.14 | 20.91 | 0.0 | - | - | - |
| demo-deadline | first | 18.23 | 30.84 | 10.8 | 5.5 | 35.31 | 0.46 | 0.0 |
| demo-deadline | second | 16.99 | 33.96 | 7.58 | 7.0 | 34.3 | 0.43 | 4.0 |
| demo-one-review-deadline | first | 29.57 | 44.39 | 14.94 | 15.5 | 34.54 | 2.32 | 0.0 |
| demo-one-review-deadline | second | 29.71 | 44.25 | 12.14 | 15.0 | 34.31 | 2.32 | 0.0 |
| analysis | first | 41.67 | 79.11 | 46.44 | 0.0 | - | - | - |
| analysis | second | 43.25 | 78.63 | 52.3 | 0.0 | - | - | - |
| chains | first | 63.52 | 72.71 | 7.15 | 0.0 | - | - | - |
| chains | second | 62.72 | 72.93 | 6.45 | 0.0 | - | - | - |
| fan-in | first | 45.33 | 51.08 | 13.93 | 0.0 | - | - | - |
| fan-in | second | 43.14 | 50.96 | 7.99 | 0.0 | - | - | - |
| claims | first | 46.34 | 63.66 | 30.55 | 0.0 | - | - | - |
| claims | second | 43.78 | 66.06 | 19.01 | 0.0 | - | - | - |
| competing | first | 43.8 | 65.75 | 20.91 | 0.0 | - | - | - |
| competing | second | 42.96 | 65.52 | 15.82 | 0.0 | - | - | - |
| time-box | first | 34.59 | 60.49 | 13.73 | 6.0 | 61.37 | 1.31 | 1.5 |
| time-box | second | 32.35 | 61.67 | 8.74 | 6.0 | 60.05 | 1.32 | 1.5 |

## Scenarios

- `demo`: `docs`: async, a review loop per unit, every review approving; 8 units, 3 slots.
- `demo-one-review`: `docs_one_review`: the same tasks as `demo`, created without waiting, so each task's successors are known early; the note does not wait for the review.
- `demo-loop`: `demo` with reviews that send the summary back (35% of first reviews, 20% of later ones).
- `demo-deadline`: `demo` under a run deadline of 15 minutes (60% of its median work over the slots), `write_note` and `report` finishing kinds.
- `demo-one-review-deadline`: `demo-one-review` under the same deadline.
- `analysis`: the analysis example: nested flows, the parsers claim `heavy` (one at a time); 5 bundles, 3 slots.
- `chains`: chains of 1, 3 and 7 tasks, the long ones queued last; 3 of each, 2 slots.
- `fan-in`: 3 fan-outs of 4 then a join, 3 of 2 then a join and 4 checks; 3 slots.
- `claims`: 6 units through a `db` claim (capacity 1) beside 6 free ones; 3 slots.
- `competing`: chains, fan-in and claims as three pipelines in one run; 3 slots.
- `time-box`: 8 topics (2 drafts, or 4 deep tasks, then `finish`) in a time box of 27 minutes (60% of the median work over the slots), `finish` a finishing kind; 3 slots.
