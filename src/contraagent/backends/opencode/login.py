"""An OpenCode key, wherever an agent finds it, and what it tells: its account and its usage.

OpenCode (opencode.ai) sells two products behind one key: Zen (pay as you go; the provider
`opencode`, omp's `opencode-zen`) and Go (a subscription with 5-hour, weekly and monthly
windows; `opencode-go`). Three coding agents run their models, each finding the key its own
way: opencode in its stored logins (`auth.json` in its data directory), pi in its own logins
then `OPENCODE_API_KEY`, omp in `OPENCODE_API_KEY`, which it also reads from `.env` files
(`omp/backend.py`). This module is the part they share:

* `stored_login` / `stored_key`: the login opencode keeps for a provider;
* `account_of_key`: the account a key bills, as `account_digest` of the key, so the same key
  is the same account on every agent and in an `api_key` credential;
* `go_usage`: the Go subscription's windows, from the usage route opencode's own console
  serves (`GET <base>/v1/usage`, `Authorization: Bearer <key>`; the route omp reads too),
  as a `RateLimit`. Every failure is None: a reading that cannot be had loses nothing else.

Nothing here writes a key or logs one.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path

from contraagent.backends.launch import ACCOUNT_SECRET, RateLimit, account_digest

#: The variable every agent reads an OpenCode key from.
KEY_VAR = "OPENCODE_API_KEY"
#: The providers an OpenCode key serves, under each agent's name for them.
PROVIDERS = frozenset({"opencode", "opencode-zen", "opencode-go"})
#: The Go subscription, the one product with usage windows.
GO = "opencode-go"
#: Where the Go usage route lives (`/v1/usage` under it), unless a gateway says otherwise.
GO_ENDPOINT = "https://opencode.ai/zen/go"
#: The usage route answers 403 to a request with no user agent of its own.
USER_AGENT = "contraagent"
USAGE_TIMEOUT_S = 10.0
#: The route's windows, by the names a Claude Code reading gives them.
_WINDOWS = {"rolling": "five_hour", "weekly": "seven_day", "monthly": "monthly"}


def is_opencode(provider: str) -> bool:
    return provider in PROVIDERS


def _store_name(provider: str) -> str:
    """The name opencode keeps a provider's login under: Zen is `opencode` there."""
    return "opencode" if provider == "opencode-zen" else provider


def auth_file(env: Mapping[str, str]) -> Path:
    """opencode's stored logins: `auth.json` in its data directory."""
    data = env.get("XDG_DATA_HOME") or str(Path(env.get("HOME") or Path.home()) / ".local" / "share")
    return Path(data) / "opencode" / "auth.json"


def stored_login(provider: str, env: Mapping[str, str]) -> dict | None:
    """The login opencode stores for `provider` (an `api` key or an `oauth` login); None
    when it stores none or the file cannot be read."""
    try:
        login = json.loads(auth_file(env).read_text()).get(_store_name(provider))
    except (OSError, ValueError, AttributeError):
        return None
    return login if isinstance(login, dict) else None


def stored_key(provider: str, env: Mapping[str, str]) -> str:
    """The key of the `api` login opencode stores for `provider`; '' when there is none."""
    login = stored_login(provider, env) or {}
    key = login.get("key") if login.get("type") == "api" else None
    return key if isinstance(key, str) else ""


def account_of_key(key: str) -> str:
    """The account `key` bills: the same digest a credential holding that key gives."""
    return account_digest(ACCOUNT_SECRET, key)


def _iso(stamp: object) -> str | None:
    if not isinstance(stamp, str):
        return None
    try:
        t = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t.astimezone(UTC).isoformat(timespec="seconds")


def _status(window: Mapping) -> str:
    """A window's state as omp names it: `exhausted` when refused or full, `warning` from 80%."""
    pct = window["percent"]
    if window.get("status") == "rate-limited" or pct >= 100:
        return "exhausted"
    return "warning" if pct >= 80 else "ok"


def go_reading(body: object, key: str = "") -> RateLimit | None:
    """The Go usage route's answer as a `RateLimit`: the rolling window as `five_hour`, the
    weekly as `seven_day`, the monthly by name in `windows`; `status` the windows' states
    but `ok` (`allowed` when every one is), as omp reports them. None for an answer missing
    a window: a partial reading would be read as a whole one."""
    usage = body.get("usage") if isinstance(body, dict) else None
    if not isinstance(usage, dict):
        return None
    windows: dict[str, dict] = {}
    states: set[str] = set()
    for field, name in _WINDOWS.items():
        w = usage.get(field)
        if not isinstance(w, dict) or isinstance(w.get("percent"), bool) or not isinstance(w.get("percent"), (int, float)):
            return None
        windows[name] = {"pct": float(w["percent"]), "resets_at": _iso(w.get("resetsAt"))}
        states.add(_status(w))
    return RateLimit(
        status="allowed" if states <= {"ok"} else ",".join(sorted(states - {"ok"})),
        five_hour_pct=windows["five_hour"]["pct"],
        five_hour_resets_at=windows["five_hour"]["resets_at"],
        seven_day_pct=windows["seven_day"]["pct"],
        seven_day_resets_at=windows["seven_day"]["resets_at"],
        observed_at=datetime.now(UTC).isoformat(timespec="seconds"),
        account=account_of_key(key),
        windows=windows,
    )


def _get(url: str, key: str, timeout: float) -> object:
    req = urllib.request.Request(url, headers={"accept": "application/json", "authorization": f"Bearer {key}", "user-agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def go_usage(
    key: str, base_url: str = "", *, timeout: float = USAGE_TIMEOUT_S, fetch: Callable[[str, str, float], object] | None = None
) -> RateLimit | None:
    """The Go subscription's usage for `key`, read from `<base_url>/v1/usage` (by default
    opencode.ai's); None with no key, on any failure, or for an answer that is not whole.
    `fetch(url, key, timeout)` replaces the request (tests)."""
    if not key:
        return None
    base = (base_url or GO_ENDPOINT).strip().rstrip("/")
    base = base[: -len("/v1")] if base.lower().endswith("/v1") else base
    try:
        body = (fetch or _get)(f"{base or GO_ENDPOINT}/v1/usage", key, timeout)
    except (OSError, ValueError, urllib.error.URLError):
        return None
    return go_reading(body, key)


def env_key(env: Mapping[str, str]) -> str:
    """`OPENCODE_API_KEY` of `env`, '' when unset or empty (which the agents read as unset)."""
    return (env.get(KEY_VAR) or "").strip()


def dotenv(path: str | os.PathLike) -> dict[str, str]:
    """`NAME=value` lines of a `.env` file (an `export ` prefix and quotes dropped, `#` lines
    skipped); empty when it cannot be read."""
    out: dict[str, str] = {}
    try:
        text = Path(path).read_text()
    except (OSError, UnicodeDecodeError):
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if name:
            out[name] = value
    return out
