"""The coding agents: one `Launch` in, one `LaunchResult` out.

Each coding agent is a `Backend` registered by name (`create_backend("claude")`); a
custom one subclasses `Backend` and is made known with `register_backend`, and its
transcript lines reach the monitor through `register_normalizer`.
"""

from contraagent._internal.backends import create_backend, register_backend
from contraagent._internal.backends.base import Backend, ModelChains
from contraagent._internal.backends.claude import ClaudeBackend
from contraagent._internal.backends.codex import CodexBackend
from contraagent._internal.backends.credentials import CredentialBinding
from contraagent._internal.backends.launch import CallUsage, Launch, LaunchResult, QuotaRefusal, Stop, Usage, account_digest
from contraagent._internal.backends.omp import OmpBackend, OmpRpcBackend
from contraagent._internal.backends.opencode import OpencodeBackend
from contraagent._internal.backends.pi import PiBackend
from contraagent._internal.backends.process import write_launch_marker
from contraagent._internal.backends.refusal import Ending, Signals
from contraagent._internal.backends.streams import normalize_stream_line, register_normalizer
from contraagent._internal.backends.wire import EventFold, LimitsWatch
from contraagent._internal.public import publish

__all__ = [
    "Backend",
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
    "Signals",
    "Stop",
    "Usage",
    "account_digest",
    "create_backend",
    "normalize_stream_line",
    "register_backend",
    "register_normalizer",
    "write_launch_marker",
]

publish(__name__, __all__)
