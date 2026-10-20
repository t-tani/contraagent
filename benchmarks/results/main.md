# Scheduling benchmark: main

contraagent 0.6.2 on Python 3.12.9, 20 seeds, one minute of agent work run in 0.2 s. Written by `benchmarks/schedule.py`, whose docstring says what each figure means. Minutes of agent work, the median over the seeds; `worst` is the largest makespan.

| scenario | run | makespan | worst | idle slot time | deferred | done by deadline | cost after deadline (USD) | would fit |
|---|---|---|---|---|---|---|---|---|
| demo | first | 35.27 | 50.99 | 9.34 | 0.0 | - | - | - |
| demo | second | 38.06 | 51.84 | 18.95 | 0.0 | - | - | - |
| demo-one-review | first | 34.2 | 50.24 | 5.2 | 0.0 | - | - | - |
| demo-one-review | second | 34.91 | 49.22 | 12.19 | 0.0 | - | - | - |
| demo-loop | first | 42.83 | 59.07 | 13.38 | 0.0 | - | - | - |
| demo-loop | second | 42.89 | 54.83 | 14.68 | 0.0 | - | - | - |
| demo-deadline | first | 22.07 | 30.17 | 10.27 | 5.0 | 35.84 | 1.08 | 2.0 |
| demo-deadline | second | 19.45 | 33.3 | 6.28 | 5.0 | 37.81 | 0.65 | 5.0 |
| demo-one-review-deadline | first | 20.19 | 35.25 | 7.71 | 6.0 | 34.31 | 0.85 | 2.0 |
| demo-one-review-deadline | second | 28.7 | 41.41 | 12.0 | 8.0 | 37.27 | 1.68 | 1.0 |
| analysis | first | 40.71 | 76.87 | 43.56 | 0.0 | - | - | - |
| analysis | second | 41.18 | 76.22 | 44.45 | 0.0 | - | - | - |
| chains | first | 60.61 | 70.79 | 4.37 | 0.0 | - | - | - |
| chains | second | 61.36 | 70.42 | 4.04 | 0.0 | - | - | - |
| fan-in | first | 43.15 | 49.26 | 9.19 | 0.0 | - | - | - |
| fan-in | second | 42.06 | 48.99 | 3.38 | 0.0 | - | - | - |
| claims | first | 44.84 | 62.62 | 26.91 | 0.0 | - | - | - |
| claims | second | 43.0 | 65.14 | 18.14 | 0.0 | - | - | - |
| competing | first | 43.08 | 61.42 | 14.75 | 0.0 | - | - | - |
| competing | second | 40.56 | 63.61 | 10.25 | 0.0 | - | - | - |
| time-box | first | 34.1 | 60.31 | 10.0 | 6.0 | 63.1 | 1.49 | 0.5 |
| time-box | second | 34.83 | 60.54 | 13.68 | 5.0 | 65.03 | 1.53 | 1.0 |

## Scenarios

- `demo`: `docs`: async, a review loop per unit, every review approving; 8 units, 3 slots.
- `demo-one-review`: `docs_one_review`: the same tasks as `demo`, one review per unit (up to 0.6.2 created without waiting); the note does not wait for the review.
- `demo-loop`: `demo` with reviews that send the summary back (35% of first reviews, 20% of later ones).
- `demo-deadline`: `demo` under a run deadline of 15 minutes (60% of its median work over the slots), `write_note` and `report` finishing kinds.
- `demo-one-review-deadline`: `demo-one-review` under the same deadline.
- `analysis`: the analysis example: nested flows, the parsers claim `heavy` (one at a time); 5 bundles, 3 slots.
- `chains`: chains of 1, 3 and 7 tasks, the long ones queued last; 3 of each, 2 slots.
- `fan-in`: 3 fan-outs of 4 then a join, 3 of 2 then a join and 4 checks; 3 slots.
- `claims`: 6 units through a `db` claim (capacity 1) beside 6 free ones; 3 slots.
- `competing`: chains, fan-in and claims as three pipelines in one run; 3 slots.
- `time-box`: 8 topics (2 drafts, or 4 deep tasks, then `finish`) in a time box of 27 minutes (60% of the median work over the slots), `finish` a finishing kind; 3 slots.
