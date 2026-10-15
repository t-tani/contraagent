# Compatibility

What a contraagent release keeps from the release before it, and what it may
change. The version is `MAJOR.MINOR.PATCH` ([SemVer](https://semver.org)).

## What is public

- **The public modules' names**: each name in the `__all__` of `contraagent`,
  `contraagent.config`, `contraagent.backends`, `contraagent.engine`,
  `contraagent.plugins`, `contraagent.monitor`, `contraagent.monitor.api` and
  `contraagent.testing`, with its signature, its fields and its documented
  behaviour. Each object has one public path, and its `__module__` names it.
- **The types they reach**: every contraagent type that a public signature, a
  field or an argument given to a callback names is exported from a public module.
- **The command line**: the commands and their options, as `contraagent --help`
  and `contraagent <command> --help` print them, and the exit codes they document.
- **The pipeline config file**: its tables and keys, as
  `examples/reference/pipeline.toml` writes every one of them and the JSON Schema
  `schemas/pipeline.schema.json` states them. A first line
  `#:schema <path to pipeline.schema.json>` in a config file gives the schema to an
  editor that reads the directive (Taplo, Even Better TOML).
- **The files a run writes**: the layout of `runs/<run>/` and the records in it, of
  the run format its `run.json` names (below).
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
- `trends.json` in a run directory: the monitor's digest of a finished run, made
  again from the run's logs whenever they change.
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
