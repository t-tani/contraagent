"""The agent directory a pi launch runs with (`PI_CODING_AGENT_DIR`).

pi reads its user configuration from one directory (`~/.pi/agent` by default): its
settings, its `SYSTEM.md` and `APPEND_SYSTEM.md`, `AGENTS.md`, extensions, skills, MCP
servers, and the logins in `auth.json`. Flags turn most of it off, but not the
settings or the system-prompt files, so a launch runs with a directory of
contraagent's own instead, made from these parts only:

    settings.json        `SETTINGS`: no project trust, no cache warming, no telemetry
    auth.json            a link to the logins of the source directory, when the credential is one
    models.json          a link to the source's custom providers (ambient), or a gateway's provider
    models-store.json    a link to the source's model catalogue
    bin/                 a link to the source's `fd` and `rg`

A link is a symbolic link; on Windows, where a user may not make one, a junction or a
hard link (`links`).

The directory is named by what it holds, so launches made alike share one: pi locks
`auth.json.lock` beside the link while it refreshes an OAuth login, and launches that
share the directory refresh one login once. A pi the user runs on the source
directory itself takes its own lock.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from contraagent._internal.backends.wire import positive_int
from contraagent._internal.platform.links import links as os_links
from contraagent._internal.runs.files import write_document

#: What every launch's `settings.json` holds: a project's `.pi/` files are never trusted
#: (with no saved decision, as in every launch, this also comes from `--no-approve`), no
#: request keeps a prompt cache warm, nothing is reported about the install.
SETTINGS = {"defaultProjectTrust": "never", "cacheWarming": "off", "enableInstallTelemetry": False, "quietStartup": True}

#: Files and directories linked from the source directory when it has them.
LINKED = ("models-store.json", "bin")


def default_source(env: dict[str, str]) -> Path:
    """The agent directory pi itself would use under `env`."""
    named = env.get("PI_CODING_AGENT_DIR")
    return Path(os.path.expanduser(named)) if named else Path.home() / ".pi" / "agent"


def default_root(env: dict[str, str]) -> Path:
    """Where contraagent keeps the agent directories it makes."""
    cache = env.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(cache) / "contraagent" / "pi"


def windows(source: Path) -> dict[str, int]:
    """The context window of each model `source` describes, by provider-qualified id: pi's
    model catalogue (`models-store.json`, `{provider: {"models": [...]}}`) and the custom
    providers (`models.json`, `{"providers": {provider: {"models": [...]}}}`), the latter
    winning, each model's `contextWindow` as listed (exact). A file that cannot be read
    adds nothing."""
    out: dict[str, int] = {}
    for name in ("models-store.json", "models.json"):
        try:
            doc = json.loads((source / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        providers = doc.get("providers") if name == "models.json" and isinstance(doc, dict) else doc
        for provider, entry in providers.items() if isinstance(providers, dict) else ():
            models = entry.get("models") if isinstance(entry, dict) else None
            for m in models if isinstance(models, list) else ():
                window = m.get("contextWindow") if isinstance(m, dict) else None
                if isinstance(m, dict) and m.get("id") and (found := positive_int(window)) is not None:
                    out[f"{provider}/{m['id']}"] = found
    return out


def make(root: Path, source: Path, *, logins: bool, models: dict | None, link_models: bool) -> Path:
    """The agent directory with `source`'s logins (`logins`), its custom providers
    (`link_models`) or the providers `models` (a `models.json` document), made once.

    Idempotent and safe from concurrent launches: every file is written to a temporary
    name and renamed into place."""
    plan: dict[str, object] = {"settings.json": SETTINGS}
    links = {name: source / name for name in LINKED if (source / name).exists()}
    if logins:
        links["auth.json"] = source / "auth.json"
    if models is not None:
        plan["models.json"] = models
    elif link_models and (source / "models.json").exists():
        links["models.json"] = source / "models.json"
    key = json.dumps({"files": plan, "links": {k: str(v) for k, v in links.items()}}, sort_keys=True)
    target = root / hashlib.sha256(key.encode()).hexdigest()[:16]
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name, doc in plan.items():
        text = json.dumps(doc, indent=2) + "\n"
        f = target / name
        if not f.is_file() or f.read_text(encoding="utf-8") != text:
            write_document(f, text)
    for name, src in links.items():
        f = target / name
        if f.is_symlink() and os.readlink(f) == str(src):
            continue
        if f.is_dir() and not f.is_symlink():
            continue  # one pi made itself before the source had it: kept
        _replace(target, name, lambda tmp, src=src: os_links.link(src, tmp))
    return target


def _replace(directory: Path, name: str, create) -> None:
    """Create the link `name` in `directory` under a temporary name with `create(path)`, then
    rename it over (a file is written by `write_document`)."""
    tmp = Path(tempfile.mktemp(prefix=f".{name}.", dir=directory))
    create(tmp)
    os.replace(tmp, directory / name)
