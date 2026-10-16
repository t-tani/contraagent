"""Plugins: an agent task's implementation, in the form the coding agent loads natively."""

from contraagent._internal.plugins.plugin import Plugin
from contraagent._internal.plugins.scaffold import new_plugin
from contraagent._internal.public import publish

__all__ = ["Plugin", "new_plugin"]

publish(__name__, __all__)
