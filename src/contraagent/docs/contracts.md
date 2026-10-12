# Contracts and validators

A **contract** is a file plus the schema it must satisfy and the validators it
must pass. An agent task's output contract comes from `agent_task(output=...,
validators=[...])`; a Python task's from its return annotation.

## Output models

Outputs are pydantic models. Define them at the top level of an importable
module, not in the script you run and not inside a function: the check inside
the agent's session imports them (`contraagent check` says when it cannot).
Their field descriptions reach the agent in the call file's JSON Schema.

::code{file="examples/demo/tasks.py" from="class Prepared(BaseModel):" to="def three_points"}

## Checked twice, by the same rules

- **Inside the session.** The plugin's stop hook runs `contraagent call
  validate`, which reads the call file (`$CONTRAAGENT_CALL`), imports the output
  model and runs the command validators. A failure keeps the agent working in
  the same turn.
- **By the runner, after the turn.** The schema, freshness (a file left by an
  earlier run does not pass) and every validator. A failure resumes the same
  session with the errors as the next turn, until the file passes or the
  resumes are spent (`invalid_output`).

Each resume is a **round**. The journal records how many rounds a task took
(`rounds`) and the errors each resume was sent (`round_errors`), and the monitor
shows each round of its transcript.

## Validators

A validator is any callable `(path, value) -> errors`. `value` is the checked
content (the model instance, or the text of a text output); an empty result
passes. Its errors go back to the agent exactly like schema errors, so they
name what is wrong and what is expected.

::code{file="examples/demo/tasks.py" from="def three_points" to="def its_own_unit"}

A rule that relates the output to what the task was given takes the task's
params as the keyword argument `params` (an agent task's as its call file holds
them; a Python task's with every upstream value resolved). A validator that
declares `call` is given the path of an agent task's call file.

::code{file="examples/demo/tasks.py" from="def its_own_unit" to="#: A linter"}

`CommandValidator` turns an external program (textlint, a structure checker)
into one: exit 0 passes, anything else fails with the program's output as the
errors. `{path}` in its arguments is the output file and `{call}` the call file,
which holds the params: a script given `{call}` checks the output against the
input, inside the agent's session too. It runs in the task's working directory,
in the runner and in the hook alike, and it runs even when the schema check
fails, so one round reports every error.

::code{file="examples/demo/tasks.py" from="#: A linter" to="#: A rule about the output"}

Given `{call}`, a command checks the output against the input, and the agent
runs it before it stops:

::code{file="examples/demo/tasks.py" from="#: A rule about the output" to="summarize = agent_task("}

::code{file="examples/demo/checks.py"}

| | Python function | `CommandValidator` |
|---|---|---|
| Runs in the runner | yes | yes |
| Runs inside the agent's session | no | yes: it travels in the call file |

## Inputs

A task that receives another task's result (a `Pending`) reads that task's file
as an **input contract**: checked before launch, and a task whose input fails is
refused (`invalid_input`) rather than run on nothing.
