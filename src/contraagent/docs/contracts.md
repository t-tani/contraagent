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

::code{file="examples/demo/tasks.py" from="class Prepared(BaseModel):" to="def three_points"}

## Checked twice, by the same rules

- **Inside the session**, on Claude Code and Codex. The plugin's stop hook runs
  `contraagent call validate`, which reads the call file (`$CONTRAAGENT_CALL`),
  imports the output model and runs the command validators. A failure keeps the
  agent working in the same turn. omp, opencode and pi have no stop hook that
  continues a session ([Coding agents](agents.md)): for them the runner's check
  below is the first one, and its errors come back in a correction round.
- **By the runner, after the turn.** The schema, freshness (a file left by an
  earlier run does not pass), the parts to keep (`preserve`, below) and every validator. A failure resumes the same
  session with the errors as the next turn, until the file passes or the
  resumes are spent (`invalid_output`).

Each launch of the session is a **round**, and each resume a **correction
round**. The journal records how many rounds a task took
(`rounds`) and the errors each resume was sent (`round_errors`), and the monitor
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
file of the latest task of that kind created so far for the same unit (or `key=`),
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
| Claude Code | `--system-prompt` | `--tools ""` | `--setting-sources ""` and `--strict-mcp-config`, as on every launch; no `--plugin-dir`, no `--agent` |
| omp | `--system-prompt`; omp still appends its environment footer (the working directory, the system) | `--no-tools --no-lsp` | the isolation overlay every launch has (no context files, skills, rules or MCP servers); no `--plugin-dir` |
| pi | `--system-prompt` | `--no-tools` | the flags every launch has (`--no-extensions`, `--no-skills`, `--no-context-files`, ...); no `--skill`, no `-e` |
| opencode | an agent of its own (`--agent`) whose `prompt` it is; opencode's free models refuse such a session | that agent's `permission` denies every tool | the user's opencode config is not read either (an empty `XDG_CONFIG_HOME`: with no tool, nothing else reads it); no plugin |

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

A task that receives another task's result (a `Pending`) reads that task's file
as an **input contract**: checked before launch, and a task whose input fails is
refused (`invalid_input`) rather than run on nothing.
