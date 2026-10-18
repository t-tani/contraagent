"""Which coding agent and model each kind of task runs on, and where it goes on a 429.

* `config.py`      `PipelineConfig`: the one TOML file
* `kind_config.py` `KindConfig`: one kind's resolved routing and budgets
* `router.py`      `Route` / `Router`: the failover chain as a circuit breaker
* `plan.py`        `RoutingPlan`: config + overrides -> per-kind config and router
* `preflight.py`   probe every route once before the first task (`PreflightPolicy`)
* `quota.py`       `CredentialRests`: credentials that rest past their quota caps
* `capacity.py`    a `PerTask` claim capacity over the host's free memory and cores
"""

from contraagent._internal.routing.config import ConfigError, PerTask, PipelineConfig
from contraagent._internal.routing.kind_config import KindConfig, configs_from_tables, require_budgets
from contraagent._internal.routing.plan import Overrides, RoutingError, RoutingPlan
from contraagent._internal.routing.preflight import PreflightPolicy, PreflightRecord, PreflightStopped
from contraagent._internal.routing.quota import CredentialRests, QuotaRule
from contraagent._internal.routing.router import Route, Router, load_fallbacks

__all__ = [
    "ConfigError",
    "KindConfig",
    "Overrides",
    "PerTask",
    "PipelineConfig",
    "PreflightPolicy",
    "PreflightRecord",
    "PreflightStopped",
    "CredentialRests",
    "QuotaRule",
    "Route",
    "Router",
    "RoutingError",
    "RoutingPlan",
    "configs_from_tables",
    "load_fallbacks",
    "require_budgets",
]
