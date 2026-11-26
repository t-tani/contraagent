# Improving a pipeline from its runs

A run on the coding agents records more than its outputs. Its journal holds the
errors that each correction sent back, the limits that stopped a launch, the tool
calls that the permissions refused and the routes that a task moved past. These
records show where the pipeline's text falls short: a role that does not state a
rule, an output model whose field says too little about what it takes, a budget too
small for the work. This page is for the coding agent that wrote the pipeline and
now improves it from what its runs recorded.

## What a run's records say

`contraagent diagnose` reads the records of one run and prints, for each kind, what
they say to change. It launches nothing and spends nothing.

```
contraagent diagnose runs/docs-1
```

The first line counts the run's tasks and how they ended. Under each kind, each
entry is one sign: one pattern in the records of that kind's tasks, with the share
of its tasks that show it. Its `tasks` line names those tasks, its `transcript` line
the transcript of the first of them that has one, and its `change` line what to
change, with the topic that explains the change, as `contraagent check` names one.
The signs are these:

- An output that did not pass one check: a validator by its name
  (`[three_points]`), a field of the output model, or the file itself (not written,
  not valid JSON). The sign also counts the tasks that still did not pass the check
  after every correction.
- A launch stopped at a limit of its budget (`max_turns`, `timeout_s`, `stall_s`,
  `max_budget_usd`, `context_budget`), or a peak context near `context_budget`.
- Calls of one tool that the permissions refused.
- A refusal or a stop by a safety classifier.
- A launch that ended for its route (a rate limit, a failed login), or a route
  passed over while its credential rested. The cause is then in the routes and
  credentials, not in the pipeline's text.
- An attempt that ended in another stop, even when its task passed on a later
  attempt, and a Python task's function that raised.
- The tasks that cost more than three times the kind's median, in USD, or in turns
  when the coding agent reports no cost, in a kind of five agent tasks or more.

The counts are of tasks. A sign in 9 of 10 tasks is a rule that the role does not
state; a sign in 1 of 10 can be a unit with more work than the others. The kinds
with no sign share one line. The command exits 0 when no kind shows a sign and 1
when one does. The [monitor](monitor.md) shows the same run to the person who runs
it, with each task's rounds, transcript and cost.

## Change one part, then run the changed tasks again

A change goes to the part of the pipeline that the sign names: the role in the
plugin, the output model's description of a field, a validator, a budget in the
config. Change one part at a time, so that the next run shows what that change did.

A new run resumed from the run that was read launches only the tasks whose
definition or inputs changed, and takes the others over from it
([Resuming from another run](tasks.md#resuming-from-another-run)):

```
contraagent run tasks.py:docs --config pipeline.toml --kwargs '{...}' --run-id docs-2 --resume-from docs-1
contraagent diagnose runs/docs-2 --against runs/docs-1
```

A change to a role changes the definition of every task of its kind, so the new run
launches all of them again, and the tasks given their outputs when those outputs
change. A run on the coding agents spends tokens, so the person who asked for the
pipeline starts it, unless they ask you to.

With `--against`, the diagnosis of the new run is followed by what changed since the
earlier run. The two runs' tasks are paired by key, and for each kind it gives:

- the parts of the fingerprint that changed (`definition`, `params`,
  `input_files`, ...), with the number of tasks for each;
- how many tasks passed and how many were sent back, and what they cost, in each run;
- the tasks that pass now and did not then (`passing now`), and the reverse
  (`failing now`);
- among the tasks that passed in both runs, those whose output differs.

The tasks that the new run took over are only counted. Two runs of different flows
can be compared too, but a task of the same key may then be other work, and the
comparison says so.

## Check a change on other units

A change made from the records of some units can fit those units and not the work:
they pass after it, and other units do not. So run the changed pipeline on units
whose records you did not read, and diagnose that run: the sign that the change was
for should be rare there too.

Each task runs once in each run, and a coding agent does not answer the same way
twice. A difference in one or two tasks can be chance; a difference across many
tasks of a kind is the change. A task that passed before and fails now is worth
reading, even when the counts of its kind improved.

## What a change should not be

- Do not write about one unit in a role. A plugin names no run, unit or file path
  ([Guide](guide.md#pitfalls)), and a rule that one unit's output broke goes into
  the role as a rule for every unit.
- Do not loosen a validator so that a wrong output passes. When a check keeps
  sending outputs back, either the role does not state the rule, or the rule is not
  the one the work needs; decide which, and change that.
- Do not raise a kind's budget for one unit that costs more than the others. Read
  that unit's transcript first.
- Do not give an output more corrections (`max_corrections`) when it is still wrong
  after the ones it has. It is not getting closer
  ([Contracts](contracts.md#checked-twice-by-the-same-rules)).
