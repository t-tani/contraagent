"""contraagent: run coding-agent CLIs as typed, supervised, observable tasks.

Think pydantic-ai for coding agents (`claude -p`, `omp -p`): the agent is
a subprocess, its contract with you is a set of files it must leave
behind, and everything around it — scheduling, failover, resume, live
monitoring — is the framework's job.

Layers, bottom up (each imports only the ones above it in this list):

* `errors`      `ContraagentError`, the base of every error raised on purpose
* `docs/`       the documentation, installed with the package: Markdown topics and the
                examples they quote; `contraagent docs`
* `dispatch/`   the domain-free `Task`/`TaskResult` envelope and the schedulers:
                `WorkQueue` (locks, caps, retry, throttle, deadline, bottom level)
                and `FlowDriver` (generator flows over it); `make_python_task`
* `backends/`   one coding-agent CLI behind `Backend`: one `Launch` in, one `LaunchResult` out
* `contracts`   `OutputContract`/`InputContract`: files checked by pydantic and
                `validators`; `run_until_valid` resumes the session until they hold;
                `calls`: the call file an agent task is handed
* `routing/`    `PipelineConfig` (one TOML file) -> `RoutingPlan`: per-kind
                `KindConfig` and failover `Router`, with a preflight
* `execution/`  `AgentRunner` (one task, with failover), `RetryingRunner`, `PythonTaskRunner`,
                `TaskAdapter`, `Run` (journal, lock, plan, resume), `CursorStore`
* `plugins/`    an agent task's implementation, as the coding agent loads it;
                hooks declared once and rendered into each agent's own hook system
* `pipeline/`   `agent_task`, `@python_task`, `Pipeline`: the API a pipeline is written in
* `monitor/`    a read-only live view of a run, as a library and a web UI
* `hub/`        the runs of many hosts in one monitor: `contraagent relay` ships a host's runs,
                `contraagent hub` stores them and serves their monitor
* `testing`     `StubAgent`: a coding agent that plays scripted replies, for tests

A pipeline declares its tasks (parameters, output, budget), implements each
agent task as a plugin, and writes the flow as a plain function:

    summarize = agent_task("summarize", plugin="plugins/summarize", params=Doc, output=Summary)

    def docs(units):
        for u in units:
            summarize(u, path=f"in/{u}.md")

    Pipeline("pipeline.toml").run(docs, units=["alpha", "beta"])
"""

from contraagent.backends import (
    AMBIENT,
    OMP_PREAMBLE,
    STDIN_THRESHOLD,
    ApiKey,
    Backend,
    Bedrock,
    ClaudeBackend,
    Credential,
    CredentialError,
    Gateway,
    Launch,
    LaunchError,
    LaunchResult,
    Limits,
    OAuthToken,
    OmpBackend,
    OmpRpcBackend,
    Pool,
    RateLimit,
    Secret,
    Stop,
    Subscription,
    Vertex,
    WorkloadIdentity,
    create_backend,
    register_backend,
)
from contraagent.backends.streams import normalize_stream_event, read_stream, register_normalizer
from contraagent.calls import CallFile
from contraagent.contracts import InputContract, OutputContract, check_input, run_until_valid
from contraagent.dispatch import (
    FlowDriver,
    ResultEnricher,
    Task,
    TaskDeferred,
    TaskFailed,
    TaskResult,
    TaskScope,
    WorkQueue,
    kind_name,
    make_python_task,
)
from contraagent.errors import ContraagentError
from contraagent.execution import (
    AgentRunner,
    CursorStore,
    PythonTaskRunner,
    RetryingRunner,
    Run,
    RunExists,
    RunLocked,
    TaskAdapter,
)
from contraagent.pipeline import CheckReport, Pending, Pipeline, RunReport, TooManyPasses, agent_task, python_task
from contraagent.plugins import Plugin, PluginError
from contraagent.routing import (
    ConfigError,
    KindConfig,
    Overrides,
    PipelineConfig,
    Route,
    Router,
    RoutingError,
    RoutingPlan,
    configs_from_tables,
    require_budgets,
)
from contraagent.validators import CommandValidator

__all__ = [
    "AMBIENT",
    "OMP_PREAMBLE",
    "STDIN_THRESHOLD",
    "AgentRunner",
    "ApiKey",
    "Backend",
    "Bedrock",
    "CallFile",
    "CheckReport",
    "ClaudeBackend",
    "CommandValidator",
    "ConfigError",
    "ContraagentError",
    "Credential",
    "CredentialError",
    "CursorStore",
    "FlowDriver",
    "Gateway",
    "InputContract",
    "KindConfig",
    "Launch",
    "LaunchError",
    "LaunchResult",
    "Limits",
    "OAuthToken",
    "OmpBackend",
    "OmpRpcBackend",
    "OutputContract",
    "Overrides",
    "Pending",
    "Pipeline",
    "PipelineConfig",
    "Plugin",
    "PluginError",
    "Pool",
    "PythonTaskRunner",
    "RateLimit",
    "ResultEnricher",
    "RetryingRunner",
    "Route",
    "Router",
    "RoutingError",
    "RoutingPlan",
    "Run",
    "RunExists",
    "RunLocked",
    "RunReport",
    "Secret",
    "Stop",
    "Subscription",
    "Task",
    "TaskAdapter",
    "TaskDeferred",
    "TaskFailed",
    "TaskResult",
    "TaskScope",
    "TooManyPasses",
    "Vertex",
    "WorkQueue",
    "WorkloadIdentity",
    "agent_task",
    "check_input",
    "configs_from_tables",
    "create_backend",
    "kind_name",
    "make_python_task",
    "normalize_stream_event",
    "python_task",
    "read_stream",
    "register_backend",
    "register_normalizer",
    "require_budgets",
    "run_until_valid",
]
