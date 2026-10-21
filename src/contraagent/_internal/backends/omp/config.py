"""omp's own config: the `retry.fallbackChains` reader (`OmpBackend.model_chains`)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from contraagent._internal.platform.commands import commands


class OmpModelChains:
    """What omp's own `retry` settings say, as omp reports them.

    Model-level failover in omp is configuration, not a flag:
    `retry.modelFallback` (default true) with `retry.fallbackChains`
    mapping a role name, an exact `provider/model-id`, `provider/*` or
    `provider/prefix/*` to an ordered list of selectors. The caller does
    not drive it — that is the decision, not an oversight. The reader
    exists so the preflight can say whether a chain is configured, since
    a `modelFallback: true` with no chains is a chain of nothing that a
    quota refusal walks past unimpeded. Documented at omp.sh/docs/roles.
    """

    def __init__(self, enabled: bool, chains: dict, unread: str = ""):
        self.enabled = enabled
        self.chains = chains
        #: Why omp did not report its settings (`omp config get ... failed: ...`); empty when it did.
        self.unread = unread

    def covers(self, model: str) -> list:
        """The selectors omp would try after `model`, in order.

        Key syntax follows the docs: an exact provider-qualified id, a
        `provider/*` wildcard, or a `provider/prefix/*` prefix wildcard.
        The longest matching prefix wins, and an exact id beats any
        wildcard.
        """
        if not self.enabled or not self.chains:
            return []
        if model in self.chains:
            return list(self.chains[model])
        prov, _, bare = model.rpartition("/")
        best: tuple[int, list] | None = None
        for key, entries in self.chains.items():
            if not key.endswith("/*"):
                continue
            head = key[:-2]
            head_prov, sep, head_prefix = head.partition("/")
            if sep:
                # provider/id-prefix/* — the provider must match exactly
                # and the id against the prefix, which may itself end in
                # a wildcard.
                ok = prov == head_prov and (bare == head_prefix or (head_prefix.endswith("*") and bare.startswith(head_prefix[:-1])))
            else:
                # provider/* — any model from that provider.
                ok = prov == head
            if ok and (best is None or len(head) > best[0]):
                best = (len(head), list(entries))
        return best[1] if best else []

    def describe(self, model: str) -> str:
        """One line saying what omp will do, and where to change it.

        The caller does not drive omp's model failover — that is the
        decision, not a gap: `retry.fallbackChains` is omp's own config
        and the operator's to set. So the useful thing this can report is
        whether a chain is configured. omp does not say which of its files
        a setting comes from, so the line names omp's config, not a file.
        """
        if self.unread:
            # Without omp's own answer its chains are not known.
            return f"not known: {self.unread}"
        if not self.enabled:
            return "off: retry.modelFallback is false in omp's config"
        if not self.chains:
            return (
                "none configured in omp's config — model failover is omp's "
                "own setting; add retry.fallbackChains there "
                "(modelFallback already defaults true)"
            )
        got = self.covers(model)
        if not got:
            return f"no chain in omp's config covers {model}"
        return "omp's config -> " + ", ".join(got)


def load_model_chains(env: dict, launch_cwd: Path, binary: str = "omp") -> OmpModelChains:
    """`retry.modelFallback` and `retry.fallbackChains` as omp reports them
    (`<binary> config get <key> --json`), run in `launch_cwd` with `env`.

    omp decides which of its files applies: the project's
    `<launch cwd>/.omp/config.yml`, the global one, PI_CODING_AGENT_DIR,
    PI_CONFIG_DIR, a named profile. So the cwd that matters is the one the
    launch carries, not whatever directory the driver was typed in. When
    omp does not answer, `describe` says why (`unread`) instead of saying
    that no chain is configured.

    `retry.modelFallback` defaults to true, so a config with no retry
    block still *claims* model failover and has none — that gap is worth
    reporting rather than passing over.
    """
    enabled = _setting(binary, env, launch_cwd, "retry.modelFallback")
    if isinstance(enabled, _Failed):
        return OmpModelChains(True, {}, unread=enabled.reason)
    chains = _setting(binary, env, launch_cwd, "retry.fallbackChains")
    if isinstance(chains, _Failed):
        return OmpModelChains(True, {}, unread=chains.reason)
    if not isinstance(chains, dict):
        return OmpModelChains(True, {}, unread="omp config get retry.fallbackChains failed: its value is not an object")
    return OmpModelChains(enabled is not False, {k: list(v) for k, v in chains.items() if isinstance(v, list)})


class _Failed:
    """Why `omp config get` gave no value."""

    def __init__(self, reason: str) -> None:
        self.reason = reason


def _setting(binary: str, env: dict, cwd: Path, key: str) -> object:
    """The value of omp's setting `key` (`config get <key> --json`'s `value`); else `_Failed`
    with why (`omp config get <key> failed: <the first line of its error output>`)."""
    failed = f"omp config get {key} failed"
    try:
        proc = subprocess.run(
            commands.resolve([binary, "config", "get", key, "--json"], env.get("PATH")),
            capture_output=True,
            text=True,
            cwd=cwd,
            env={**env, "NO_COLOR": "1"},
            encoding="utf-8",
            errors="replace",
        )
    except OSError as e:
        return _Failed(f"{failed}: {e}")
    if proc.returncode != 0:
        # omp writes the error first, then a hint ("Run 'omp config list' ..."): the first line says what failed.
        said = (proc.stderr or "").strip().splitlines()
        return _Failed(f"{failed}: {said[0].strip()}" if said else f"{failed}: exit code {proc.returncode}")
    try:
        answer = json.loads(proc.stdout)
    except ValueError:
        return _Failed(f"{failed}: its output is not JSON")
    if not isinstance(answer, dict) or "value" not in answer:
        return _Failed(f"{failed}: its output has no value")
    return answer["value"]
