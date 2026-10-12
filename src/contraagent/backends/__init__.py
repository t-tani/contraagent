"""Coding-agent CLIs behind one interface: one `Launch` in, one `LaunchResult` out.

* `base.py`         the `Backend` ABC (and `OneShotBackend` for spawn-then-parse CLIs)
* `launch.py`       the backend-neutral vocabulary: `Launch`, `Limits`, `LaunchResult`, `Stop`, `Usage`
* `credentials.py`  credential types (subscription, API key, OAuth token, WIF, Bedrock, ...) and secrets
* `process.py`      the guarded subprocess loop every CLI backend shares
* `live_processes.py`  the agent processes this interpreter started, for teardown
* `streams.py`      raw transcript lines -> the monitor's renderable events
* `claude/`, `omp/` the concrete CLIs

The registry below is the one place a coding-agent *name* (what a config
file, a `Route` or a journal row says) is tied to a class. Everything that
needs the list of known agents reads it from here.
"""

from __future__ import annotations

from contraagent.backends.base import Backend, OneShotBackend
from contraagent.backends.claude import ClaudeBackend
from contraagent.backends.credentials import (
    AMBIENT,
    Ambient,
    ApiKey,
    Bedrock,
    Credential,
    CredentialBase,
    CredentialBinding,
    CredentialError,
    Gateway,
    OAuthToken,
    Pool,
    Secret,
    Subscription,
    Vertex,
    WorkloadIdentity,
)
from contraagent.backends.launch import STDIN_THRESHOLD, Launch, LaunchResult, Limits, RateLimit, Stop, Usage
from contraagent.backends.omp import OMP_PREAMBLE, OmpBackend, OmpRpcBackend
from contraagent.backends.process import LaunchError

_REGISTRY: dict[str, type[Backend]] = {
    "claude": ClaudeBackend,
    "omp": OmpBackend,
    "omp-rpc": OmpRpcBackend,
}


def register_backend(name: str, cls: type[Backend]) -> None:
    """Make a custom `Backend` subclass known by `name` (config files, routes, `create_backend`)."""
    _REGISTRY[name] = cls


def backend_class(name: str) -> type[Backend] | None:
    """The class registered under `name`, or None."""
    return _REGISTRY.get(name)


def known_agents() -> tuple[str, ...]:
    """Every registered coding-agent name, in registration order."""
    return tuple(_REGISTRY)


def create_backend(name: str, **kwargs) -> Backend:
    """A new backend for a registered name. Unknown names raise KeyError."""
    cls = _REGISTRY.get(name)
    if cls is None:
        raise KeyError(f"unknown backend: {name} (known: {', '.join(_REGISTRY)})")
    return cls(**kwargs)


__all__ = [
    "AMBIENT",
    "OMP_PREAMBLE",
    "STDIN_THRESHOLD",
    "Ambient",
    "ApiKey",
    "Backend",
    "Bedrock",
    "ClaudeBackend",
    "Credential",
    "CredentialBase",
    "CredentialBinding",
    "CredentialError",
    "Gateway",
    "Launch",
    "LaunchError",
    "LaunchResult",
    "Limits",
    "OAuthToken",
    "OmpBackend",
    "OmpRpcBackend",
    "OneShotBackend",
    "Pool",
    "RateLimit",
    "Secret",
    "Stop",
    "Subscription",
    "Usage",
    "Vertex",
    "WorkloadIdentity",
    "backend_class",
    "create_backend",
    "known_agents",
    "register_backend",
]
