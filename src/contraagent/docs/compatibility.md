# Compatibility

What a contraagent release keeps from the release before it, and what it may
change. The version is `MAJOR.MINOR.PATCH` ([SemVer](https://semver.org)).

## What is public

- **The public modules' names**: each name in the `__all__` of `contraagent`,
  `contraagent.config`, `contraagent.backends`, `contraagent.engine`,
  `contraagent.plugins`, `contraagent.monitor`, `contraagent.monitor.api` and
  `contraagent.testing`, with its signature, its fields and its documented
  behaviour. Each object has one public path, and a class's or a function's
  `__module__` names it (a type alias, such as `PanelBody`, has none of its own).
- **The types they reach**: every contraagent type that a public signature, a
  field or an argument given to a callback names is exported from a public module:
  a class; a protocol, the type of a function a user writes (a quota rule, a scope, a
  validator, a panel, a callback), whose docstring states the call; or an alias, a
  union of exported types. An alias of literal values is not a type of its own: the
  annotation lists its values (`Task.executor: Literal["agent", "python"]`).
- **The command line**: the commands and their options, as `contraagent --help`
  and `contraagent <command> --help` print them, and the exit status each `--help`
  states at its end.
- **The pipeline config file**: its tables and keys, as
  `examples/reference/pipeline.toml` writes every one of them and the JSON Schema
  `schemas/pipeline.schema.json` states them. A first line
  `#:schema <path to pipeline.schema.json>` in a config file gives the schema to an
  editor that reads the directive (Taplo, Even Better TOML).
- **The files a run writes**: the layout of `runs/<run>/` and the records in it, of
  the run format its `run.json` names, as [the run directory](#the-run-directory)
  lists them.
- **The monitor's HTTP API**: the endpoints and responses of the OpenAPI document
  `contraagent monitor --openapi PATH` writes, versioned by its `api_version`
  (`/api/info`): its major part goes up when a field is removed, renamed or changes
  meaning, its minor part when one is added.
- **The hub's protocol**: what relays send a hub, the OpenAPI document
  `contraagent hub --openapi PATH` writes. A hub is upgraded before its relays
  ([Operating a hub](hub-operations.md)).

`contraagent docs --path` prints where these documents are; `schemas/` holds the
JSON Schemas, and the documentation site serves them under `/schemas/`.

## What is not public

- `contraagent._internal`, and any name that starts with `_`.
- The wording of a message: an exception's text, a log line, a warning, a `repr`.
  The exception's class is public.
- A transcript's lines (`streams/<file>.stream.jsonl`): they are what the coding
  agent printed, in its own format.
- The files of a run directory that [the run directory](#the-run-directory) marks
  as not public.
- The page the monitor serves. The npm packages `@contraagent/api`,
  `@contraagent/ui` and `@contraagent/elements` have versions and documentation of
  their own.

## Changes that break nothing

- A new public name, module, command or option.
- A new optional parameter with a default, or a new keyword-only parameter with
  a default.
- A new field of a record, of a response, or of a type a callback is given. A
  reader of a record or a response ignores a field it does not know; a journal row
  keeps the row extras a pipeline adds.
- A new value of a journal row's `stop` or of a deferral's `cause`.
- A new table or key in the config file.

## Versions

| Release | May break the public API | Says so in |
|---|---|---|
| `0.x.0` (a minor release before 1.0) | yes | `CHANGELOG.md`: each break under Changed or Removed, a renamed name as old → new |
| `0.x.y` (a patch release before 1.0) | no | |
| `x.0.0` from 1.0 (a major release) | yes | `CHANGELOG.md`, and the deprecation warnings of the releases before it |
| `x.y.0`, `x.y.z` from 1.0 | no | |

## Deprecation

From 1.0, a public name, parameter, option or config key that a major release
removes or renames first warns for at least two minor releases: using it warns
with `ContraagentDeprecationWarning`, which names what replaces it. Before 1.0, a minor release renames or removes without a warning, and
`CHANGELOG.md` names the replacement.

## The run directory

`runs/<run>/` holds one run. A file that is public keeps its path and its form within
a run format; one marked "run format only" keeps its path, and its content is read
through the monitor's API, which is public.

| Path | What it is | Public |
|---|---|---|
| `run.json` | the run: who drives it, its arguments, its format, its preflight and quota caps | yes: `run.schema.json` |
| `journal.jsonl` | one row per finished attempt | yes: `journal.schema.json` |
| `launches.jsonl` | one row per launch of a coding agent | yes: `launches.schema.json` |
| `plan.jsonl` | every task the flow created | yes: `plan.schema.json` |
| `flow_calls.jsonl` | each flow call's start and end | yes: `flow_calls.schema.json` |
| `deferred.jsonl` | each deferred task and its cause | yes: `deferred.schema.json` |
| `rests.jsonl` | each start and end of a credential's quota rest | yes: `rests.schema.json` |
| `cursor.json` | a resume cursor (`CursorStore`), when a pipeline keeps one | yes: `cursor.schema.json` |
| `calls/<key>.json` | the call file an agent task's launch was given | yes: the model `contraagent.backends.CallFile` |
| `out/` | the tasks' outputs, at the paths their kinds' `output_name` gives | yes: each one's schema is its task's output |
| `out/<...>.message.txt` | the whole final message beside an output taken out of it (`unwrap`) | yes: plain text |
| `pipeline/<name>.jsonl`, `pipeline/<name>.json` | the pipeline's own log and document (`contraagent.log`, `contraagent.save`) | yes: the rows and the values the pipeline wrote |
| `contracts/<key>.json`, `definitions/<kind>.json` | what each task and each kind declared | run format only |
| `inflight/<key>.json` | a marker per task that is running | run format only |
| `streams/<file>.stream.jsonl` | each agent task's transcript | the path only: the lines are the coding agent's |
| `trends.json` | the monitor's digest of a finished run, made again from the logs whenever they change | no |

Beside the run directory, `runs/<run>.lock` is the run lock, and a relay keeps its
place in `<runs-dir>.relay.json` ([the hub](hub.md)); neither is public. A
recording directory (`--record DIR`) is laid out as [testing](testing.md) shows.
What contraagent writes outside these is listed in
[Coding agents](agents.md#directories-outside-the-run).

## Run formats and schemas

`run.json` names the run format of its run directory: `format`, a whole number.
This release writes run format 1 and reads run format 1. A `run.json` without
`format` is of run format 1.

| File | JSON Schema (in `schemas/`) |
|---|---|
| `run.json` | `run.schema.json` |
| `journal.jsonl` | `journal.schema.json` (one line) |
| `launches.jsonl` | `launches.schema.json` (one line) |
| `plan.jsonl` | `plan.schema.json` (one line) |
| `flow_calls.jsonl` | `flow_calls.schema.json` (one line) |
| `deferred.jsonl` | `deferred.schema.json` (one line) |
| `rests.jsonl` | `rests.schema.json` (one line) |
| `cursor.json` | `cursor.schema.json` |
| the config file (`pipeline.toml`) | `pipeline.schema.json` |

- **What changes the run format**: a record or a field removed or renamed, a field
  whose type or meaning changes, another layout. A new field or a new record does
  not.
- **Resume**: `Run` (and so `Pipeline.run(..., resume=True)` and
  `contraagent run --resume`) refuses a run directory of a run format the release
  does not read with `RunFormatError`, and leaves the directory as it is. Resume it
  with the release that wrote it, or start a new run id.
- **Reading**: the monitor, an export, a relay and a hub read run directories of
  every run format the release reads. From 1.0, a release reads every run format
  that the releases of its major version wrote. A release that writes a new run
  format, or stops reading one, says so in `CHANGELOG.md`.
