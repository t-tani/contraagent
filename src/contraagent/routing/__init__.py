"""Which coding agent and model each kind of task runs on, and where it goes on a 429.

* `config.py`      `PipelineConfig`: the one TOML file
* `kind_config.py` `KindConfig`: one kind's resolved routing and budgets
* `router.py`      `Route` / `Router`: the failover chain as a circuit breaker
* `plan.py`        `RoutingPlan`: config + overrides -> per-kind config and router
* `preflight.py`   probe every route once before the first task
"""

from contraagent.routing.config import ConfigError, PipelineConfig
from contraagent.routing.kind_config import KindConfig, configs_from_tables, require_budgets
from contraagent.routing.plan import Overrides, RoutingError, RoutingPlan
from contraagent.routing.router import Route, Router, load_fallbacks

__all__ = [
    "ConfigError",
    "KindConfig",
    "Overrides",
    "PipelineConfig",
    "Route",
    "Router",
    "RoutingError",
    "RoutingPlan",
    "configs_from_tables",
    "load_fallbacks",
    "require_budgets",
]
