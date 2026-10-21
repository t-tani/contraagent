"""contraagent's implementation. The public modules (`contraagent`, `contraagent.config`,
`contraagent.backends`, `contraagent.engine`, `contraagent.plugins`, `contraagent.monitor`,
`contraagent.monitor.api`, `contraagent.testing`) re-export from it; nothing here imports
one of them.

Layers, bottom up (each imports only the ones above it in this list):

* `errors`      `ContraagentError`, the base of every error raised on purpose
* `platform/`   the host, on Linux, macOS and Windows alike: its processes (`processes`),
                a child in a group of its own (`groups`), a file lock (`locks`), a file
                replaced while others read it (`sharing`), and the line and variables that name a live agent process's run and task
                (`telemetry`, `envvars`); leaf modules, importing nothing else of the package
* `commandline` the parts every command's arguments share; a leaf module
* `public`      how a public module publishes what it re-exports
* `docs`        the documentation installed with the package (`contraagent/docs/`): its
                topics and the examples they quote; `contraagent docs`
* `runs/`       run records: the layout of a run directory, the one writer of a document
                and of a log line, the readers of complete lines, the times records hold;
                `RunSource` (where runs are read from) and `Liveness`
* `dispatch/`   the domain-free `Task`/`TaskResult` envelope and the schedulers:
                `WorkQueue` (claims, caps, retry, throttle, deadline, bottom level, priority)
                and `FlowDriver` (async flows over it, on its `FlowLoop`); `make_python_task`;
                `records`: the facts a run records (hops, rests, deferral causes, flow
                paths), one type each
* `backends/`   one coding-agent CLI behind `Backend`: one `Launch` in, one `LaunchResult` out
* `contracts/`  `OutputContract`/`InputContract` (`contract`): files checked by pydantic and
                `validators`; `run_until_valid` resumes the session until they hold;
                `calls`: the call file an agent task is handed; `pointers`: the parts of a
                JSON output a task keeps (`agent_task(preserve=)`); `input_file`:
                `InputFile`, a file a task is given by its path and the hash of its content
* `routing/`    `PipelineConfig` (one TOML file) -> `RoutingPlan`: per-kind
                `KindConfig` and failover `Router`, with a preflight
* `execution/`  `AgentRunner` (one task, with failover), `RetryingRunner`, `PythonTaskRunner`,
                `TaskAdapter`, `Run` (journal, lock, plan, resume), `CursorStore`
* `plugins/`    an agent task's implementation, as the coding agent loads it;
                hooks declared once and rendered into each agent's own hook system
* `pipeline/`   `agent_task`, `@python_task`, `Pipeline`: the API a pipeline is written in
* `monitor/`    a read-only live view of a run, as a library and a web UI (`static/`, built
                from `web/`) with its OpenAPI document (`openapi.json`)
* `hub/`        the runs of many hosts in one monitor: `contraagent relay` ships a host's runs,
                `contraagent hub` stores them and serves their monitor; only `hub/server.py`,
                which serves the monitor's app, imports `monitor/`
* `testing`     `StubAgent`: a coding agent that plays scripted replies, for tests
* `cli`         `contraagent ...`: one argument tree over every command
"""
