"""Plugins: the implementation of agent tasks, in the form the coding agent loads natively.

* `plugin.py`    `Plugin`: a plugin directory (roles, skills, settings, hooks)
* `hooks.py`     hooks declared once in `hooks.toml`, rendered into each agent's own hook system
* `lint.py`      `lint_plugin`: do the parts still agree?
* `scaffold.py`  `new_plugin`: a working template (`contraagent plugin new`)
"""

from contraagent._internal.plugins.lint import lint_plugin
from contraagent._internal.plugins.plugin import Plugin, PluginError, is_plugin
from contraagent._internal.plugins.scaffold import new_plugin

__all__ = ["Plugin", "PluginError", "is_plugin", "lint_plugin", "new_plugin"]
