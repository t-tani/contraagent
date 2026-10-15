"""The coding agents: one `Launch` in, one `LaunchResult` out.

Each coding agent is a `Backend` registered by name (`create_backend("claude")`); a
custom one subclasses `Backend` and is made known with `register_backend`, and its
transcript lines reach the monitor through `register_normalizer`. The launch of an agent
task hands its agent a call file (`CallFile.path_of(launch)`): its params and its output.
"""

from contraagent._internal.backends import create_backend, register_backend
from contraagent._internal.backends.base import Backend, ModelChains
from contraagent._internal.backends.claude import ClaudeBackend
from contraagent._internal.backends.codex import CodexBackend
from contraagent._internal.backends.credentials import CredentialBinding
from contraagent._internal.backends.launch import CallUsage, Launch, LaunchResult, QuotaRefusal, Stop, Usage
from contraagent._internal.backends.omp import OmpBackend, OmpRpcBackend
from contraagent._internal.backends.opencode import OpencodeBackend
from contraagent._internal.backends.pi import PiBackend
from contraagent._internal.backends.process import Sink
from contraagent._internal.backends.refusal import Ending, Signals
from contraagent._internal.backends.streams import normalize_stream_line, register_normalizer
from contraagent._internal.backends.wire import EventFold, LimitsWatch
from contraagent._internal.contracts.calls import CallFile, CallOutput, SchemaRef
from contraagent._internal.public import publish

__all__ = [
    "Backend",
    "CallFile",
    "CallOutput",
    "CallUsage",
    "ClaudeBackend",
    "CodexBackend",
    "CredentialBinding",
    "Ending",
    "EventFold",
    "Launch",
    "LaunchResult",
    "LimitsWatch",
    "ModelChains",
    "OmpBackend",
    "OmpRpcBackend",
    "OpencodeBackend",
    "PiBackend",
    "QuotaRefusal",
    "SchemaRef",
    "Signals",
    "Sink",
    "Stop",
    "Usage",
    "create_backend",
    "normalize_stream_line",
    "register_backend",
    "register_normalizer",
]

publish(__name__, __all__)
