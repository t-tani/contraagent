"""The common base of every error contraagent raises on purpose.

Each layer defines its own errors next to the code that raises them
(`ConfigError`, `RoutingError`, `CredentialError`, `LaunchError`, `RunLocked`,
`PluginError`); all of them derive from `ContraagentError`, so a caller can
tell "contraagent refused" from a bug with one `except`. This module imports
nothing else from the package, so any layer can use it.
"""

from __future__ import annotations

import difflib


class ContraagentError(Exception):
    """An error contraagent raises deliberately: bad config, an unusable credential, a lock held elsewhere."""


def did_you_mean(word: str, options) -> str:
    """` (did you mean x?)` for the closest of `options`, or "": for messages about a name."""
    close = difflib.get_close_matches(word, sorted(options), n=1, cutoff=0.6)
    return f" (did you mean {close[0]}?)" if close else ""
