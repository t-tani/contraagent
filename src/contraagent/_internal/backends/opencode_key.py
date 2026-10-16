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
* `go_usage`: the Go subscription's windows, from the usage endpoint opencode's own console
  serves (`GET <base>/v1/usage`, `Authorization: Bearer <key>`; the endpoint omp reads too),
  as a `QuotaReading`. Every failure is None: a reading that cannot be had loses nothing else;
* `OpencodeKeyAccount`: an agent's account and Go usage from the key it bills (opencode, pi).

Nothing here writes a key or logs one.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path

from contraagent._internal.backends.credentials import Credential, CredentialError
from contraagent._internal.backends.launch import ACCOUNT_SECRET, Launch, account_digest
from contraagent._internal.dispatch.records import QuotaReading, QuotaWindow
from contraagent._internal.runs.times import iso_of, now_iso, parse_iso

#: The variable every agent reads an OpenCode key from.
KEY_VAR = "OPENCODE_API_KEY"
#: The providers an OpenCode key serves, under each agent's name for them.
PROVIDERS = frozenset({"opencode", "opencode-zen", "opencode-go"})
#: The Go subscription, the one product with usage windows.
GO = "opencode-go"
#: Where the Go usage endpoint lives (`/v1/usage` under it), unless a gateway says otherwise.
GO_ENDPOINT = "https://opencode.ai/zen/go"
#: The usage endpoint answers 403 to a request with no user agent of its own.
USER_AGENT = "contraagent"
USAGE_TIMEOUT_S = 10.0
#: The endpoint's windows, by the names a Claude Code reading gives them.
_GO_WINDOWS = {"rolling": "five_hour", "weekly": "seven_day", "monthly": "monthly"}


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
        login = json.loads(auth_file(env).read_text(encoding="utf-8")).get(_store_name(provider))
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


def _status(window: Mapping) -> str:
    """A window's state as omp names it: `exhausted` when refused or full, `warning` from 80%."""
    pct = window["percent"]
    if window.get("status") == "rate-limited" or pct >= 100:
        return "exhausted"
    return "warning" if pct >= 80 else "ok"


def go_reading(body: object, key: str = "") -> QuotaReading | None:
    """The Go usage endpoint's answer as a `QuotaReading`: the rolling window as `five_hour`, the
    weekly as `seven_day`, the monthly by name in `windows`; `status` the windows' states
    but `ok` (`allowed` when every one is), as omp reports them. None for an answer missing
    a window: a partial reading would be read as a whole one."""
    usage = body.get("usage") if isinstance(body, dict) else None
    if not isinstance(usage, dict):
        return None
    windows: dict[str, QuotaWindow] = {}
    states: set[str] = set()
    for field, name in _GO_WINDOWS.items():
        w = usage.get(field)
        if not isinstance(w, dict) or isinstance(w.get("percent"), bool) or not isinstance(w.get("percent"), (int, float)):
            return None
        windows[name] = QuotaWindow(
            pct=float(w["percent"]), resets_at=iso_of(at.timestamp()) if (at := parse_iso(w.get("resetsAt"))) else None
        )
        states.add(_status(w))
    return QuotaReading.from_windows(
        windows,
        status="allowed" if states <= {"ok"} else ",".join(sorted(states - {"ok"})),
        observed_at=now_iso(),
        account=account_of_key(key),
    )


def _get(url: str, key: str, timeout: float) -> object:
    req = urllib.request.Request(url, headers={"accept": "application/json", "authorization": f"Bearer {key}", "user-agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def go_usage(
    key: str, base_url: str = "", *, timeout: float = USAGE_TIMEOUT_S, fetch: Callable[[str, str, float], object] | None = None
) -> QuotaReading | None:
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
        text = Path(path).read_text(encoding="utf-8")
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


class OpencodeKeyAccount:
    """The account and the Go usage of an agent that bills OpenCode models to an OpenCode key
    it finds its own way (`opencode_key`); opencode and pi. omp reports its own usage."""

    def billed_key(self, credential: Credential, model: str) -> tuple[str, str]:
        """The OpenCode key a launch of `model` as `credential` bills, and the endpoint it goes
        to ('' for opencode.ai's); ('', '') for another provider."""
        raise NotImplementedError

    def account(self, credential: Credential, model: str = "") -> str:
        """For an OpenCode model: the account of the key the launch bills, the same digest
        opencode, omp and pi give for that key. '' for any other provider."""
        try:
            key, _ = self.billed_key(credential, model)
        except (CredentialError, ValueError, KeyError):
            return ""
        return account_of_key(key)

    def usage_reading(self, launch: Launch) -> QuotaReading | None:
        """The OpenCode Go subscription's windows for the launch's key, from OpenCode's usage
        endpoint (the agent reports none itself); None for another model or when it cannot be read."""
        if not launch.model.startswith(GO + "/"):
            return None
        try:
            key, base = self.billed_key(launch.credential, launch.model)
        except (CredentialError, ValueError, KeyError):
            return None
        return go_usage(key, base)
