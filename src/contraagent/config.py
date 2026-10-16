"""Routing and identity: credentials, routes, a kind's budgets, quota readings.

`PipelineConfig` (in `contraagent`) reads them from `pipeline.toml`; these are the
values it holds, and a `quota_rule` is given a `QuotaReading`.
"""

from contraagent._internal.backends.credentials import (
    AMBIENT,
    Ambient,
    ApiKey,
    Bedrock,
    Credential,
    Gateway,
    OAuthToken,
    Pool,
    Secret,
    Subscription,
    Vertex,
    WorkloadIdentity,
)
from contraagent._internal.backends.launch import Limits
from contraagent._internal.dispatch.records import QuotaReading, QuotaWindow
from contraagent._internal.public import publish
from contraagent._internal.routing.kind_config import KindConfig
from contraagent._internal.routing.router import Route

__all__ = [
    "AMBIENT",
    "Ambient",
    "ApiKey",
    "Bedrock",
    "Credential",
    "Gateway",
    "KindConfig",
    "Limits",
    "OAuthToken",
    "Pool",
    "QuotaReading",
    "QuotaWindow",
    "Route",
    "Secret",
    "Subscription",
    "Vertex",
    "WorkloadIdentity",
]

publish(__name__, __all__)
