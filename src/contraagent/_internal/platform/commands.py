"""The program a command line names, as the OS starts it, and the bash a hook runs under.

A command line is built as the coding agent's documentation writes it (`claude -p ...`),
and recorded so. The OS starts it differently:

* POSIX (Linux, macOS): as it is; the OS finds the program on PATH (`PosixCommands`).
* Windows: the OS adds only `.exe` to a bare name, while a CLI installed by npm is a
  batch file (`claude.cmd`), which runs under `cmd.exe` and has `cmd.exe` read its
  arguments, a prompt among them, so `%`, `^`, `&` and `"` in them would be read as
  `cmd.exe`'s own. So the program is looked up on PATH as the shell would
  (`shutil.which`, which tries each of PATHEXT), and a batch file that npm made is run as
  the program it starts (its `.exe`, or `node` with its script): the arguments then reach
  the program unchanged. A batch file that is not npm's is refused (`CommandError`)
  (`WindowsCommands`).

A plugin's hook scripts run under bash on every OS (`bash`): on Windows that is the bash
of Git for Windows, which Claude Code runs its own hooks with there, never the `bash.exe`
of System32, which starts WSL, where the plugin's Windows paths do not exist.

`commands` is this OS's; each takes the lookup it uses in its constructor, so each can be
tested on any OS.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Protocol

Which = Callable[[str, str | None], str | None]

#: The variables that name the bash a hook runs under on Windows, first to last: this
#: package's (`envvars.BASH`) and Claude Code's.
BASH_VARIABLES = ("CONTRAAGENT_BASH", "CLAUDE_CODE_GIT_BASH_PATH")


class CommandError(OSError):
    """A command line the OS cannot start with its arguments unchanged."""


class Commands(Protocol):
    def resolve(self, argv: list[str], path: str | None = None) -> list[str]:
        """The command line to start for `argv`, its program looked up on `path` (PATH when
        None). Raises `CommandError` for a program that cannot be passed its arguments."""
        ...

    def bash(self, env: Mapping[str, str] | None = None) -> str | None:
        """The bash a hook script runs under, in the environment `env` (this process's when
        None); None when there is none."""
        ...


class PosixCommands:
    """A command line starts as it is; a hook runs under the `bash` on PATH."""

    def resolve(self, argv: list[str], path: str | None = None) -> list[str]:
        return list(argv)

    def bash(self, env: Mapping[str, str] | None = None) -> str | None:
        return "bash"


#: What an npm batch file runs: `"%~dp0\\node_modules\\...\\cli.js"` or `"%dp0%\\..."`.
_NPM_TARGET = re.compile(r'"%(?:~dp0|dp0%)\\([^"%]+)"')
_SCRIPTS = (".js", ".mjs", ".cjs")


def _which(name: str, path: str | None) -> str | None:
    return shutil.which(name, path=path)


class WindowsCommands:
    """The program looked up as the shell would; an npm batch file replaced by what it runs.
    `which(name, path)` is given in a test."""

    def __init__(self, which: Which | None = None) -> None:
        self._which = which or _which

    def resolve(self, argv: list[str], path: str | None = None) -> list[str]:
        if not argv:
            return []
        found = self._which(argv[0], path)
        if found is None:
            return list(argv)  # the OS reports it missing, as it would
        if Path(found).suffix.lower() not in (".cmd", ".bat"):
            return [found, *argv[1:]]
        return [*self._npm_target(Path(found), path), *argv[1:]]

    def bash(self, env: Mapping[str, str] | None = None) -> str | None:
        """The first of `BASH_VARIABLES` set, else a `bash` on PATH outside System32, else
        the one Git for Windows installs in Program Files."""
        env = os.environ if env is None else env
        for name in BASH_VARIABLES:
            if env.get(name):
                return env[name]
        found = self._which("bash", env.get("PATH"))
        if found and "\\system32\\" not in found.lower().replace("/", "\\"):
            return found
        for root in (env.get("ProgramFiles"), env.get("ProgramFiles(x86)")):
            if root and (Path(root) / "Git" / "bin" / "bash.exe").is_file():
                return str(Path(root) / "Git" / "bin" / "bash.exe")
        return None

    def _npm_target(self, batch: Path, path: str | None) -> list[str]:
        try:
            text = batch.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise CommandError(f"{batch}: {exc.strerror}") from exc
        targets = _NPM_TARGET.findall(text)
        if not targets:
            raise CommandError(f"{batch} is a batch file, whose arguments cmd.exe would read as its own: name the program it runs instead")
        target = batch.parent / targets[-1]  # the last one: the program, after the node.exe it may look for
        if target.suffix.lower() not in _SCRIPTS:
            return [str(target)]
        local = batch.parent / "node.exe"
        node = str(local) if local.is_file() else self._which("node", path)
        if node is None:
            raise CommandError(f"{batch} runs {target} with node, and node is not on PATH")
        return [node, str(target)]


#: This OS's commands.
commands: Commands = WindowsCommands() if sys.platform == "win32" else PosixCommands()
