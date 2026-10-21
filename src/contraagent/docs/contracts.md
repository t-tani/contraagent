# Contracts and validators

A **contract** is a file plus the schema it must satisfy and the validators it
must pass. An agent task's output contract comes from `agent_task(output=...,
validators=[...])`; a Python task's from its return annotation.

## Output models

Outputs are pydantic models. Define them at the top level of an importable
module, not in the script you run and not inside a function: the check inside
the agent's session imports them (`contraagent check` says when it cannot).
Their field descriptions reach the agent in the call file's JSON Schema. Each
model's `examples` (its **example**) is what a stub run writes in place of the
agent; give it one that passes the validators ([Checking and testing](testing.md)).

::code{file="examples/demo/tasks.py" from="class Prepared(BaseModel):" to="class SummarizeParams"}

## Rows

An output may be a list that grows as the agent works: the findings of a review,
the items of a long analysis. `output=Rows[Finding]` declares a JSON Lines file
whose every line is one `Finding`, a **row**. The prompt asks the agent to add
each row to the file as soon as it has it, one line at a time, and the call file
says the format (`output.format` is `jsonl`, and `output.json_schema` is the
schema of one row). The file is `{kind}/{unit}.jsonl` by default (`{kind}/{kind}.jsonl`
for a task with no unit).

::code{file="examples/rows/flow.py" from="class Finding(" to="@python_task"}

Each line is checked against the row's model. A line that does not parse, or does
not meet the model, fails the whole output, and its errors name the line:
`line 3: line: Input should be greater than or equal to 1 (got: 0)`. The
correction round sends those errors back, so the agent corrects the lines named
and keeps the rest. A file that is one JSON array is named as such. A blank line
is no row, and a file with no row is an empty list.

As a value, rows are a `Rows`, a `list` of the models in the file's order. A
validator is given that list, the flow receives it, and a task it is passed to
gets it: a Python task as a list of models (`list[Finding]`), an agent task as a
list of JSON objects in its call file. The example a stub run writes is one row,
the example of the row's model. A Python task may return rows too
(`-> Rows[Finding]`, returning `Rows([...])`). `preserve` and `unwrap` take a JSON
document, not rows.

## A launch stopped for its time

The runner stops a launch past its `timeout_s` (`timeout`) or silent for its
`stall_s` (`stalled`), and the task fails, whatever the agent had written. A long
task often has written something useful by then. `partial_on` names the stops
after which it is kept: `agent_task(partial_on=["timeout", "stalled"])`, or
`partial_on` in `[tasks.<kind>]`.

After such a stop, the output is checked as after any round: it must exist, be
written by this attempt (a file from an earlier run does not count), and pass its
schema and every validator. When it passes, the task's result is **partial**, as
when a Python task returns `Partial` ([Partial results](tasks.md#partial-results)): ok, stop `partial`, its reason the launch's
stop (`timeout`, `stalled`), and the flow receives the output. The hop keeps the
launch's own stop. A resume runs the task again, with the tasks that wait for it.
When the output fails, the task fails on the stop as before; a stopped launch is
never sent a correction round. A test plays such a launch on the stub agent with
`writes(value, stop=Stop.TIMEOUT)` (`Stop` from `contraagent.backends`;
[Checking and testing](testing.md)).

With rows, the rows written so far are the output. A last line with no newline
after it that is not valid JSON was being written when the launch was stopped:
the runner removes that line before the check.

::code{file="examples/rows/flow.py" from="review = agent_task(" to="def review_unit("}

Only these two stops are kept. Both are the runner's own: it ended the launch for
time, and the agent said nothing about its work. A turn cap (`max_turns`), a cost
cap (`budget`) or a context cap (`context_budget`) is a limit a pipeline sets to
bound a launch's spend, and a refusal, an API error or a refused credential says
the work went wrong; those fail the task as before. An output in the final message
does not exist after a stopped launch, so `partial_on` takes an output the agent
writes to a file; `contraagent check` reports a kind whose config sets it for one
that does not.

## Checked twice, by the same rules

- **Inside the session**, on Claude Code, Codex and omp. The plugin's stop hook
  runs `contraagent call validate`, which reads the call file (`$CONTRAAGENT_CALL`),
  imports the output model and runs the command validators. A failure keeps the
  agent working in the same turn. opencode and pi have no stop hook that
  continues a session ([Coding agents](agents.md)): for them the runner's check
  below is the first one, and its errors come back in a correction round.
- **By the runner, after the turn.** The schema, freshness (a file left by an
  earlier run does not pass), the parts to keep (`preserve`, below) and every validator. A failure resumes the same
  session with the errors as the next turn, until the file passes or the
  correction rounds are spent (`invalid_output`).

Each launch of the session is a **round**, and each resume a **correction
round**. A kind has 3 correction rounds after its first round by default.
`max_corrections` sets another number, from 0 to 20: `agent_task(max_corrections=1)`,
or `max_corrections` in `[tasks.<kind>]`, which outranks the declaration
([routing](routing.md#precedence)). With 0
the first failed check ends the task `invalid_output`. A short output, such as a
verdict, rarely needs more than one round to correct its form; an output that is
still wrong after many rounds is not getting closer, and each round is a full turn
of a session whose context grows. `contraagent check` reports a value out of range.

The journal records how many rounds a task took
(`rounds`), how many correction rounds its kind allowed (`max_corrections`) and the
errors each resume was sent (`round_errors`), and the monitor
shows each round of its transcript. The run's progress line for the attempt
names the first round's first error. The attempt's cost is its rounds' cost,
each round counted once: Claude Code reports a resumed session's cost so far,
omp each launch's own (`Backend.cost_is_session_total`), and `launches.jsonl`
keeps each round's own (`round_costs`).

## An output in the final message

A task that needs no tool (a verdict, a classification) may give its output as
its final message: `agent_task(..., output_from="message")`. The call file says so
(`output.from`), the agent ends with the output as its whole message and writes
no file, and the runner writes that message to the output file and checks it
there, by the same schema and validators. A message that fails its checks goes
back to the same session as the next round, asking for the corrected output as
the reply. The stop hook leaves it to the runner: the message exists only after
the turn. It saves the turn a `Write` takes, and the permission to write.

By default the whole message must be the document. A model that is told so
still puts a sentence before it now and then, or a fence around it, and each
time costs a round. `unwrap=True` takes the document out of the message instead:
the last fenced block that parses, else the longest
JSON object or array in the message. The document is the output file, the whole
message is kept beside it (`<output>.message.txt`), and the run's progress line
and `launches.jsonl` (`unwrapped`) say that it was taken out. A message that holds
no document is checked as it is, and goes back as before.

::code{file="examples/review/flow.py" from="# A verdict needs no tool" to="revise = agent_task("}

## Parts of a file to keep

A task may fill in a file that holds values already: a Python task writes a
report's items, and an agent task writes their summaries into the same file.
`output_of` names the task declaration whose file it writes: for each task, the
file of the latest task of that kind created so far for the same unit (or key),
else the file that kind's `output_name` names for it. The task waits for the
latest task created so far that writes that file, of any kind, so two never write
it at once. `output` is the schema of the whole file after the task.
`preserve` names the parts the agent must keep as they were, as JSON pointers
(RFC 6901: `/source`, `/items/0/id`), with one extension: a segment `*` is every
member of an array or object, so `/items/*/id` is the id of every item.

::code{file="examples/preserve/flow.py" from="class Item("}

Before the first round the runner reads the file and takes the values the
pointers select in it. After each round, each of them must still be in the file,
equal; one that is not is an error like any other check's, and goes back to the
same session: `/items/1/id changed: it must stay "alpha-2" (now "alpha-9")`,
`/source removed: it must stay "inputs/alpha.md"`. A pointer selects by
position, so an agent that reorders a list changes the values at its indexes.
An attempt that does not pass puts the file back as it was, so the next attempt
starts from the same values. A file that is missing before the launch, or that
does not parse, keeps nothing.

The call file lists the pointers (`output.preserve`), and the prompt tells the
agent to read the file first. The stop hook does not judge them: it sees the file
after the turn only. `preserve` takes a JSON output the agent writes, not a text
output nor one in the final message, and each pointer is checked against the
output's schema when the task is declared: `/sorce` is refused there.

## A judgement in one turn: a light launch

Such a task still starts with all that a coding agent loads before its first
turn: its own system prompt and the definitions of its tools, and it spends a
turn reading its call file. A task declared with no tools, `tools=()`, is
launched light instead:

- its role's text without the frontmatter (for a task with no plugin, its
  `instructions`) replaces the coding agent's system prompt;
- the agent gets no tool, and no plugin, settings file, skill, hook or MCP server
  is loaded;
- the prompt holds the call itself: the params as JSON and the output's JSON
  Schema (the call file is still written, for the record);
- its final message is its output, so it needs `output_from="message"`; a message
  that fails its checks goes back to the same session, as above.

::code{file="examples/light/flow.py" from="class Classified(" to="def items("}

A light launch is one call, and a small one. Measured on Haiku with a one-line
judgement:

| | light launch | the same judgement, the agent's defaults | the same task as its role, with tools |
|---|---|---|---|
| Claude Code | 1 call, 644 tokens of input (1,180 with a role and a schema) | 1 call, 16,863 (25 tools) | 2 calls, 2,230 each: `--agent` already puts the role in place of the default system prompt, and `tools: Read` keeps one tool |
| omp | 1 call, 369 (658) | 1 call, 11,828 | 2 calls, 12,311 each: omp keeps its own system prompt and every tool |

The journal row holds the first call's input (`usage.resident`), and the monitor
shows it on the tokens of each attempt. Each coding agent does it with its own flags:

| | system prompt | tools | settings, skills, MCP servers |
|---|---|---|---|
| Claude Code | `--system-prompt-file` | `--tools ""` | `--setting-sources ""` and `--strict-mcp-config`, as on every launch; no `--plugin-dir`, no `--agent` |
| omp | `--system-prompt=<file>`; omp still appends its environment footer (the working directory, the system) | `--no-tools --no-lsp` | the isolation overlay every launch has (no context files, skills, rules or MCP servers); no `--plugin-dir` |
| pi | `--system-prompt <file>` | `--no-tools` | the flags every launch has (`--no-extensions`, `--no-skills`, `--no-context-files`, ...); no `--skill`, no `-e` |
| opencode | an agent of its own (`--agent`) whose `prompt` is `{file:<file>}`; opencode's free models refuse such a session | that agent's `permission` denies every tool | the user's opencode config is not read either (an empty `XDG_CONFIG_HOME`: with no tool, nothing else reads it); no plugin |

Each `<file>` is a file in the launch's scratch directory that holds the system prompt.
The params can make the instructions long, and a command line does not take a long
text ([Coding agents](agents.md)).

Codex runs no light launch: a coding agent that cannot launch so is refused for a
kind with `tools=()`, on every route of the kind, failover hops included
(`Backend.light_launch`; [Coding agents](agents.md)). The
agent can read nothing and run nothing: give it all it needs in its params. A
list of tool names is not taken, since each coding agent names its tools its own
way; a role names the ones it may use (`tools:`), as [plugins](plugins.md) says.

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

A Python validator runs in the runner's process, in its current directory, for an
agent task and a Python task alike: a relative path it opens (one from `params`)
resolves there, not against the task's working directory (`Pipeline(cwd=)`, or the
`cwd` of its call options), which is where the coding agent and its
`CommandValidator`s run, and which a validator takes as `cwd`. `contraagent run` runs both in the directory it is started
in; a test that passes `Pipeline(cwd=project)` runs the Python code in pytest's
directory, so it calls `monkeypatch.chdir(project)` too.

::code{file="examples/demo/tasks.py" from="def its_own_unit" to="#: A linter"}

A rule about what the task changed takes `before`: the file as it was before the
task, parsed as `value` is (the model instance, or the text), or None when there
was no file or it did not meet its schema then. It is the file ahead of the
task's first round, on every correction round alike, so a round is judged by
all that the task changed, not by what it changed since the last round. The
runner reads the file ahead of the task only for a contract with such a
validator, and an attempt that does not pass puts the file back as it was, so
the next attempt has the same `before`. A Python task's validators get the
same: the file before its function was called.

::code{file="examples/before/flow.py" from="def adds_an_idea" to="def backlogs"}

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
| Takes `before` | yes | no: it reads the file as it is |

## Inputs

A task is given values, not files. Another task's output reaches it through the
flow, which awaits that task, receives the checked output at the `await` and passes it
on (see [Tasks](tasks.md#flows-that-depend-on-results)). An output that did not pass its
checks raises `TaskFailed` there, so no task is ever given it: an output its validators
rejected (`invalid_output`) meets its schema and still raises. A `partial` result
succeeded: the flow receives its output. The params themselves are checked at the task
call: an agent task's instance of its params model again under the model, a Python
task's against its parameters' annotations as it starts (`invalid_input`).

A task of a pipeline reads no other task's file as it starts. A large input is given as
an input file (`InputFile`): its path and hash are taken at the task call, and a file
that no longer has that content as the task is about to start refuses the task
(`invalid_input`; see [Tasks](tasks.md#large-inputs-input-files)). The file a task fills
in (`output_of`) is read then for its fingerprint, and checked as its output after the
launch, and the task's outside state is worked out then, a function that raises
refusing the task. Nothing else is checked when a task starts.

An **input contract** (`InputContract`) is a file a task reads, checked before launch,
for a runner built on the engine (`TaskAdapter.input_contracts`), not for a pipeline: a
file that is missing or off its schema refuses the task (`invalid_input`) rather than run
it on nothing.
