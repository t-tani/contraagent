# Scheduling benchmark: main

contraagent 0.12.0 (commit d409a78) on Python 3.12.9, 20 seeds, one minute of agent work run in 0.2 s. Written by `benchmarks/schedule.py`, whose docstring says what each figure means. Minutes of agent work, the median over the seeds; `worst` is the largest makespan.

| scenario | run | makespan | worst | idle slot time | deferred | done by deadline | cost after deadline (USD) | would fit |
|---|---|---|---|---|---|---|---|---|
| demo | first | 37.27 | 52.85 | 14.19 | 0.0 | - | - | - |
| demo | second | 38.39 | 54.2 | 16.63 | 0.0 | - | - | - |
| demo-one-review | first | 35.61 | 51.07 | 7.96 | 0.0 | - | - | - |
| demo-one-review | second | 36.02 | 54.01 | 13.13 | 0.0 | - | - | - |
| demo-loop | first | 43.77 | 58.06 | 16.93 | 0.0 | - | - | - |
| demo-loop | second | 43.95 | 55.4 | 17.85 | 0.0 | - | - | - |
| demo-deadline | first | 21.76 | 34.3 | 15.07 | 5.0 | 35.45 | 0.84 | 2.0 |
| demo-deadline | second | 20.52 | 33.5 | 7.89 | 5.0 | 37.61 | 0.79 | 5.0 |
| demo-one-review-deadline | first | 18.42 | 41.14 | 9.34 | 5.5 | 34.4 | 0.83 | 2.0 |
| demo-one-review-deadline | second | 28.46 | 43.38 | 14.35 | 8.0 | 34.94 | 1.45 | 1.0 |
| analysis | first | 39.8 | 75.19 | 41.54 | 0.0 | - | - | - |
| analysis | second | 41.42 | 75.97 | 45.92 | 0.0 | - | - | - |
| chains | first | 60.61 | 71.17 | 4.04 | 0.0 | - | - | - |
| chains | second | 61.28 | 70.77 | 3.69 | 0.0 | - | - | - |
| fan-in | first | 43.86 | 50.25 | 11.01 | 0.0 | - | - | - |
| fan-in | second | 42.58 | 49.56 | 5.17 | 0.0 | - | - | - |
| claims | first | 45.74 | 63.7 | 29.08 | 0.0 | - | - | - |
| claims | second | 43.18 | 64.35 | 18.7 | 0.0 | - | - | - |
| competing | first | 43.19 | 62.18 | 16.24 | 0.0 | - | - | - |
| competing | second | 40.78 | 63.56 | 10.91 | 0.0 | - | - | - |
| time-box | first | 34.34 | 60.07 | 9.82 | 6.0 | 61.9 | 1.53 | 1.0 |
| time-box | second | 36.05 | 60.64 | 13.21 | 5.0 | 62.08 | 1.55 | 1.0 |

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
