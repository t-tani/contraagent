"""omp's own config/registry: the `retry.fallbackChains` reader and the
`omp models --json` catalogue parser.

A leaf relative to `omp.py`: both are self-contained readers of omp's own
on-disk config or CLI output, with no dependency on the Backend contract
itself. `omp.py` is the only importer; nothing here imports back into it.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

# `omp models` is a local registry read. Generous because a cold provider
# list can be slower than the ~1.7s it takes here, and a timeout on the
# cheap preflight pass must not read as "every model is unknown".
CATALOGUE_TIMEOUT_S = 30


def parse_models(stdout: str) -> dict[str, int | None]:
    """Each model of `omp models --json` (`{"models": [{"selector", "contextWindow"}]}`),
    by its provider-qualified selector, with its context window (None where omp lists
    none). Empty when the output is not that document."""
    try:
        doc = json.loads(stdout)
    except ValueError:
        return {}
    rows = doc.get("models") if isinstance(doc, dict) else None
    out: dict[str, int | None] = {}
    for m in rows if isinstance(rows, list) else ():
        if not isinstance(m, dict):
            continue
        selector = m.get("selector") or (f"{m['provider']}/{m['id']}" if m.get("provider") and m.get("id") else None)
        if not isinstance(selector, str):
            continue
        window = m.get("contextWindow")
        out[selector] = window if isinstance(window, int) and not isinstance(window, bool) and window > 0 else None
    return out


class OmpModelChains:
    """What omp's own `retry:` block says, read from its config.

    Model-level failover in omp is configuration, not a flag:
    `retry.modelFallback` (default true) with `retry.fallbackChains`
    mapping a role name, an exact `provider/model-id`, `provider/*` or
    `provider/prefix/*` to an ordered list of selectors. The caller does
    not drive it — that is the decision, not an oversight. The reader
    exists so the preflight can say whether a chain is configured and
    name the file to edit, since a `modelFallback: true` with no chains
    is a chain of nothing that a quota refusal walks past unimpeded.
    Documented at omp.sh/docs/roles.
    """

    def __init__(self, enabled: bool, chains: dict, source=None):
        self.enabled = enabled
        self.chains = chains
        self.source = source

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
        whether a chain is configured, and the file to edit if not.
        """
        got = self.covers(model)
        where = self.source or "omp config"
        if not self.chains:
            return (
                f"none configured in {where} — model failover is omp's "
                f"own setting; add retry.fallbackChains there "
                f"(modelFallback already defaults true)"
            )
        if not got:
            return f"no chain in {where} covers {model}"
        return f"{where} -> " + ", ".join(got)


def load_model_chains(env: dict, launch_cwd: Path) -> OmpModelChains:
    """Read `retry:` from omp's config, project first then global.

    Both locations are omp's, not ours to guess. The project file is
    `<launch cwd>/.omp/config.yml` and omp checks that one directory
    only, not ancestors — so the cwd that matters is the one the launch
    carries, not whatever directory the driver was typed in. The global
    one is whatever `omp config path` reports, which already accounts
    for PI_CODING_AGENT_DIR, PI_CONFIG_DIR and a named profile.

    `retry.modelFallback` defaults to true, so a config with no retry
    block still *claims* model failover and has none — that gap is worth
    reporting rather than passing over.
    """
    import yaml

    agent_dir = _omp_agent_dir(env)
    candidates = [launch_cwd / ".omp" / "config.yml", agent_dir / "config.yml", Path.home() / ".omp" / "agent" / "config.yml"]
    for cand in candidates:
        try:
            data = yaml.safe_load(cand.read_text()) or {}
        except (OSError, ValueError, yaml.YAMLError):
            continue
        if not isinstance(data, dict):
            continue
        retry = data.get("retry")
        if not isinstance(retry, dict):
            continue
        chains = retry.get("fallbackChains")
        chains = chains if isinstance(chains, dict) else {}
        return OmpModelChains(bool(retry.get("modelFallback", True)), {k: list(v) for k, v in chains.items() if isinstance(v, list)}, cand)
    return OmpModelChains(True, {}, candidates[-1])


def _omp_agent_dir(env: dict) -> Path:
    """omp's active agent directory, as it reports it."""
    if shutil.which("omp", path=env.get("PATH")):
        try:
            proc = subprocess.run(
                ["omp", "config", "path"], capture_output=True, text=True, timeout=CATALOGUE_TIMEOUT_S, env={**env, "NO_COLOR": "1"}
            )
            out = (proc.stdout or "").strip().splitlines()
            if proc.returncode == 0 and out:
                return Path(out[-1].strip())
        except (OSError, subprocess.SubprocessError):
            pass
    return Path.home() / ".omp" / "agent"
