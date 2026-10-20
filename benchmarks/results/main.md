# Scheduling benchmark: main

contraagent 0.6.2 on Python 3.12.9, 20 seeds, one minute of agent work run in 0.2 s. Written by `benchmarks/schedule.py`, whose docstring says what each figure means. Minutes of agent work, the median over the seeds; `worst` is the largest makespan.

| scenario | run | makespan | worst | idle slot time | deferred | done by deadline | cost after deadline (USD) | would fit |
|---|---|---|---|---|---|---|---|---|
| demo | first | 35.07 | 52.0 | 10.75 | 0.0 | - | - | - |
| demo | second | 37.47 | 49.64 | 15.93 | 0.0 | - | - | - |
| demo-loop | first | 42.56 | 58.7 | 14.88 | 0.0 | - | - | - |
| demo-loop | second | 43.02 | 54.05 | 14.7 | 0.0 | - | - | - |
| demo-deadline | first | 19.71 | 30.12 | 9.78 | 5.0 | 36.19 | 0.75 | 2.0 |
| demo-deadline | second | 19.57 | 33.29 | 8.38 | 5.0 | 37.73 | 0.65 | 5.0 |
| analysis | first | 39.41 | 74.88 | 38.16 | 0.0 | - | - | - |
| analysis | second | 39.91 | 75.49 | 40.72 | 0.0 | - | - | - |
| chains | first | 60.7 | 71.21 | 3.3 | 0.0 | - | - | - |
| chains | second | 60.85 | 70.3 | 3.52 | 0.0 | - | - | - |
| fan-in | first | 43.13 | 50.04 | 10.28 | 0.0 | - | - | - |
| fan-in | second | 42.5 | 49.17 | 4.11 | 0.0 | - | - | - |
| claims | first | 45.04 | 62.86 | 27.31 | 0.0 | - | - | - |
| claims | second | 43.02 | 65.03 | 18.91 | 0.0 | - | - | - |
| competing | first | 42.63 | 61.33 | 14.88 | 0.0 | - | - | - |
| competing | second | 40.63 | 62.93 | 10.11 | 0.0 | - | - | - |
| time-box | first | 33.98 | 59.96 | 9.91 | 6.0 | 63.1 | 1.4 | 1.0 |
| time-box | second | 34.04 | 60.55 | 7.24 | 5.0 | 60.27 | 1.65 | 0.5 |

`demo-one-review` was not run: this version refuses a task call's `Pending` among the params of another task call.

`demo-one-review-deadline` was not run: this version refuses a task call's `Pending` among the params of another task call.

## Scenarios

- `demo`: `docs`: async, a review loop per unit, every review approving; 8 units, 3 slots.
- `demo-loop`: `demo` with reviews that send the summary back (35% of first reviews, 20% of later ones).
- `demo-deadline`: `demo` under a run deadline of 15 minutes (60% of its median work over the slots), `write_note` and `report` finishing kinds.
- `analysis`: the analysis example: nested flows, the parsers claim `heavy` (one at a time); 5 bundles, 3 slots.
- `chains`: chains of 1, 3 and 7 tasks, the long ones queued last; 3 of each, 2 slots.
- `fan-in`: 3 fan-outs of 4 then a join, 3 of 2 then a join and 4 checks; 3 slots.
- `claims`: 6 units through a `db` claim (capacity 1) beside 6 free ones; 3 slots.
- `competing`: chains, fan-in and claims as three pipelines in one run; 3 slots.
- `time-box`: 8 topics (2 drafts, or 4 deep tasks, then `finish`) in a time box of 27 minutes (60% of the median work over the slots), `finish` a finishing kind; 3 slots.
