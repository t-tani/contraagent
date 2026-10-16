"""contraagent: run coding-agent CLIs as typed, supervised, observable tasks.

A pipeline declares its tasks (parameters, output, budget), implements each agent task as
a plugin, and writes the flow as a plain function:

    from contraagent import Pipeline, agent_task

    summarize = agent_task("summarize", plugin="plugins/summarize", params=Doc, output=Summary)

    def docs(units):
        for u in units:
            summarize(u, path=f"in/{u}.md")

    Pipeline("pipeline.toml").run(docs, units=["alpha", "beta"])

The public modules: `contraagent` (this one: tasks, flows, the pipeline, validators, the
values callbacks are given, the errors), `contraagent.config` (credentials, routes,
budgets, quota readings), `contraagent.backends` (the coding agents), `contraagent.engine`
(the runners and schedulers underneath a pipeline), `contraagent.plugins`,
`contraagent.monitor` (with `contraagent.monitor.api`, its HTTP responses) and
`contraagent.testing`. `contraagent docs` prints the documentation.
"""

from contraagent._internal.backends.credentials import CredentialError
from contraagent._internal.backends.process import LaunchError
from contraagent._internal.contracts.rows import Rows
from contraagent._internal.contracts.validators import CommandValidator, Validator
from contraagent._internal.dispatch.flow import TaskDeferred, TaskFailed, time_box
from contraagent._internal.dispatch.interceptors import ResultEnricher, TaskScope
from contraagent._internal.dispatch.records import Changes, DeferralCause, Frame, Hop, Loop, OtherModel, SkippedHop, TokenUsage
from contraagent._internal.dispatch.task import Origin, Partial, Task, TaskResult, TimeBox
from contraagent._internal.errors import ContraagentDeprecationWarning, ContraagentError
from contraagent._internal.execution.pipeline_files import NoCurrentRun, log, pipeline_table, save
from contraagent._internal.execution.recording import RecordingError
from contraagent._internal.execution.run import RunExists, RunFormatError, RunLocked
from contraagent._internal.execution.services import Service, service_address
from contraagent._internal.pipeline.check import CheckReport
from contraagent._internal.pipeline.graph import Pending, TextOutput, TooManyPasses
from contraagent._internal.pipeline.pipeline import Pipeline, RunReport
from contraagent._internal.pipeline.spec import AgentTask, PythonTask, agent_task, python_task
from contraagent._internal.plugins.plugin import PluginError
from contraagent._internal.public import publish
from contraagent._internal.routing.config import ConfigError, PerTask, PipelineConfig
from contraagent._internal.routing.plan import Overrides, RoutingError
from contraagent._internal.routing.preflight import PreflightStopped
from contraagent._internal.routing.quota import QuotaRule

__all__ = [
    "AgentTask",
    "Changes",
    "CheckReport",
    "CommandValidator",
    "ConfigError",
    "ContraagentDeprecationWarning",
    "ContraagentError",
    "CredentialError",
    "DeferralCause",
    "Frame",
    "Hop",
    "LaunchError",
    "Loop",
    "NoCurrentRun",
    "Origin",
    "OtherModel",
    "Overrides",
    "Partial",
    "Pending",
    "PerTask",
    "Pipeline",
    "PipelineConfig",
    "PluginError",
    "PreflightStopped",
    "PythonTask",
    "QuotaRule",
    "RecordingError",
    "ResultEnricher",
    "RoutingError",
    "Rows",
    "RunExists",
    "RunFormatError",
    "RunLocked",
    "RunReport",
    "Service",
    "SkippedHop",
    "Task",
    "TaskDeferred",
    "TaskFailed",
    "TaskResult",
    "TaskScope",
    "TextOutput",
    "TimeBox",
    "TokenUsage",
    "TooManyPasses",
    "Validator",
    "agent_task",
    "log",
    "pipeline_table",
    "python_task",
    "save",
    "service_address",
    "time_box",
]

publish(__name__, __all__)
